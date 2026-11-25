"""
SkillSwap FastAPI backend (talks to Supabase Postgres via PostgREST + RPC, Redis for locks/heartbeats)

requirements.txt
    fastapi
    uvicorn[standard]
    httpx
    redis>=5
    pyjwt
    sentence-transformers      # 384-dim all-MiniLM-L6-v2, matches vector(384) in the schema
    pydantic>=2

.env
    SUPABASE_URL=https://<project>.supabase.co
    SUPABASE_ANON_KEY=...
    SUPABASE_SERVICE_KEY=...          # server only, never ship to the browser
    REDIS_URL=rediss://default:<pw>@<host>.upstash.io:6379
    JITSI_DOMAIN=meet.yourdomain.com  # must be a JWT-enabled Jitsi (self-hosted or 8x8 JaaS)
    JITSI_APP_ID=skillswap
    JITSI_APP_SECRET=<shared secret>
    FRONTEND_ORIGIN=http://localhost:3000

Run:  uvicorn skillswap_backend:app --reload
(Split into routers/services once it grows: auth.py, booking.py, session.py, disputes.py, admin.py.)
"""
import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt  # PyJWT
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://localhost:54321").rstrip("/")
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "mock-anon-key")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "mock-service-key")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
JITSI_DOMAIN = os.environ.get("JITSI_DOMAIN", "meet.example.com")
JITSI_APP_ID = os.environ.get("JITSI_APP_ID", "skillswap")
JITSI_APP_SECRET = os.environ.get("JITSI_APP_SECRET", "change-me")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
JWT_SECRET = os.environ.get("JWT_SECRET", "skillswap-dev-secret-ucs503-2026")
USE_LOCAL_DB = os.environ.get("USE_LOCAL_DB", "1") == "1" or "localhost" in SUPABASE_URL

import skillswap_ledger
skillswap_ledger.init_db()

LOCK_TTL_SECONDS = 30            # QR6
HEARTBEAT_TTL_SECONDS = 30
JOIN_EARLY = timedelta(minutes=10)
ROOM_AFTER_END = timedelta(minutes=15)
SWEEP_INTERVAL_SECONDS = 30

http: httpx.AsyncClient
redis: aioredis.Redis
_embedder = None


# ----------------------------------------------------------------------------
# lifespan: shared clients + no-show sweeper
# ----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global http, redis
    http = httpx.AsyncClient(timeout=15)
    skillswap_ledger.init_db()
    sweeper = None
    try:
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.ping()
        sweeper = asyncio.create_task(no_show_sweeper())
    except Exception as e:
        print(f"[Warning] Redis not connected ({e}). Running with local in-memory fallback.")
        redis = None

    yield

    if sweeper:
        sweeper.cancel()
    await http.aclose()
    if redis:
        await redis.aclose()


app = FastAPI(title="SkillSwap API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------------
# Supabase helpers
# ----------------------------------------------------------------------------
ERROR_MAP = {
    "SLOT_UNAVAILABLE": (409, "This slot is no longer available."),
    "INSUFFICIENT_BALANCE": (402, "Not enough credits. Teach a session to earn more."),
    "OWN_SLOT": (400, "You cannot book your own slot."),
    "FORBIDDEN": (403, "You are not part of this booking."),
    "ADMIN_ONLY": (403, "Admin access required."),
    "NOT_SETTLEABLE": (409, "This session has already been settled."),
    "ALREADY_SETTLED": (409, "This session is already settled, so a dispute can no longer be raised."),
    "ALREADY_RESOLVED": (409, "This dispute was already resolved."),
    "INVALID_SPLIT": (422, "Split amount must be between 1 and cost - 1."),
    "INVALID_OUTCOME": (422, "Outcome must be refund_learner, pay_mentor or split."),
    "NOT_REFUNDABLE": (409, "Escrow is no longer held for this booking."),
    "duplicate key": (409, "A dispute is already open for this session."),
}


def raise_from_pg(r: httpx.Response):
    try:
        msg = r.json().get("message", "") + " " + r.json().get("details", "")
    except Exception:
        msg = r.text
    for key, (code, text) in ERROR_MAP.items():
        if key in msg:
            raise HTTPException(code, text)
    raise HTTPException(500, f"Database error: {msg[:200]}")


def _headers(token: Optional[str], service: bool):
    if service:
        return {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    return {"apikey": ANON_KEY, "Authorization": f"Bearer {token or ANON_KEY}"}


async def rpc(fn: str, params: dict, token: Optional[str] = None, service: bool = False):
    r = await http.post(f"{SUPABASE_URL}/rest/v1/rpc/{fn}", json=params, headers=_headers(token, service))
    if r.status_code >= 400:
        raise_from_pg(r)
    return r.json() if r.content else None


async def select(table: str, params: dict, token: Optional[str] = None, service: bool = False):
    r = await http.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params, headers=_headers(token, service))
    if r.status_code >= 400:
        raise_from_pg(r)
    return r.json()


async def insert(table: str, row: dict, token: Optional[str] = None, service: bool = False):
    h = {**_headers(token, service), "Prefer": "return=representation"}
    r = await http.post(f"{SUPABASE_URL}/rest/v1/{table}", json=row, headers=h)
    if r.status_code >= 400:
        raise_from_pg(r)
    return r.json()


async def patch(table: str, match: dict, values: dict, token: Optional[str] = None, service: bool = False):
    h = {**_headers(token, service), "Prefer": "return=representation"}
    r = await http.patch(f"{SUPABASE_URL}/rest/v1/{table}", params=match, json=values, headers=h)
    if r.status_code >= 400:
        raise_from_pg(r)
    return r.json()


# ----------------------------------------------------------------------------
# Auth: validate token via local JWT secret or Supabase Auth
# ----------------------------------------------------------------------------
class Caller(BaseModel):
    id: str
    token: str
    email: Optional[str] = None
    role: str = "peer"


async def current_user(authorization: str = Header(default="")) -> Caller:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1]

    # 1. Try local JWT verification
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        email = payload.get("email")
        role = payload.get("role", "peer")
        if user_id:
            try:
                prof = skillswap_ledger.get_profile_data(user_id)
                if prof.get("status") == "suspended":
                    raise HTTPException(403, "Account suspended: contact an admin")
                return Caller(id=user_id, token=token, email=email, role=role)
            except Exception:
                return Caller(id=user_id, token=token, email=email, role=role)
    except jwt.PyJWTError:
        pass

    # 2. Fallback to Supabase Auth if remote is configured
    if "localhost" not in SUPABASE_URL:
        r = await http.get(f"{SUPABASE_URL}/auth/v1/user", headers={"apikey": ANON_KEY, "Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            raise HTTPException(401, "Invalid or expired session")
        u = r.json()
        prof = await select("profiles", {"id": f"eq.{u['id']}", "select": "status,suspension_reason,role"}, service=True)
        if prof and prof[0]["status"] == "suspended":
            raise HTTPException(403, f"Account suspended: {prof[0].get('suspension_reason') or 'contact an admin'}")
        role = prof[0].get("role", "peer") if prof else "peer"
        return Caller(id=u["id"], token=token, email=u.get("email"), role=role)

    raise HTTPException(401, "Invalid or expired session token")


async def require_admin(user: Caller = Depends(current_user)) -> Caller:
    if user.role != "admin":
        raise HTTPException(403, "Admin access required.")
    return user


# ----------------------------------------------------------------------------
# SPRINT 1: US-01 Campus SSO & Authentication
# ----------------------------------------------------------------------------
@app.get("/config")
async def get_app_config():
    return {
        "starter_credits": skillswap_ledger.DEFAULT_STARTER_CREDITS,
        "campus_domain": "thapar.edu",
        "campus_node": "Campus Peer Exchange (UCS503)",
    }


class CampusLoginIn(BaseModel):
    email: str = Field(min_length=3)
    full_name: Optional[str] = None
    department: Optional[str] = "Computer Science & Engineering"
    study_year: Optional[int] = 3


@app.post("/auth/campus-sso")
async def campus_sso_login(
    body: CampusLoginIn,
    x_sso_simulate_down: Optional[str] = Header(default=None),
):
    if os.environ.get("SSO_FORCE_UNAVAILABLE") == "1" or x_sso_simulate_down == "true":
        raise HTTPException(
            status_code=503,
            detail="Campus SSO Identity Provider is currently unavailable. Please check campus network or try again later.",
        )

    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Please provide a valid campus email address (e.g., student@campus.edu).")

    full_name = body.full_name or email.split("@")[0].replace(".", " ").title()

    try:
        user_data = skillswap_ledger.register_or_login_campus_user(
            campus_email=email,
            full_name=full_name,
            department=body.department,
            study_year=body.study_year or 3,
        )
    except skillswap_ledger.AccountSuspendedError as se:
        raise HTTPException(
            status_code=403,
            detail=f"Account suspended: {se.reason}",
        )
    except skillswap_ledger.SSOUnavailableError as ue:
        raise HTTPException(
            status_code=503,
            detail=str(ue),
        )
    except Exception as e:
        raise HTTPException(500, f"Authentication error: {str(e)}")

    # Sign JWT token (valid for 7 days)
    payload = {
        "sub": user_data["id"],
        "email": user_data["campus_email"],
        "full_name": user_data["full_name"],
        "role": user_data.get("role", "peer"),
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"token": token, "user": user_data}


@app.get("/auth/me")
async def get_current_user_profile(user: Caller = Depends(current_user)):
    profile = skillswap_ledger.get_profile_data(user.id)
    return profile


@app.post("/auth/logout")
async def logout():
    return {"ok": True, "message": "Successfully logged out."}


# ----------------------------------------------------------------------------
# SPRINT 1: US-02 Manage Skill Profile
# ----------------------------------------------------------------------------
class ProfileUpdateIn(BaseModel):
    bio: Optional[str] = None
    department: Optional[str] = None
    study_year: Optional[int] = None


class SkillAddIn(BaseModel):
    skill_name: str = Field(min_length=1)
    kind: str = Field(pattern="^(offered|desired)$")
    level: str = Field(pattern="^(beginner|intermediate|advanced)$")
    hourly_rate_credits: Optional[int] = 1
    description: Optional[str] = None


@app.get("/profile/me")
async def get_my_profile(user: Caller = Depends(current_user)):
    return skillswap_ledger.get_profile_data(user.id)


@app.put("/profile/me")
async def update_my_profile(body: ProfileUpdateIn, user: Caller = Depends(current_user)):
    return skillswap_ledger.update_profile(
        user_id=user.id,
        bio=body.bio,
        department=body.department,
        study_year=body.study_year,
    )


@app.get("/skills")
async def list_skills_catalog():
    conn = skillswap_ledger.get_connection()
    skills = conn.execute("SELECT * FROM skills ORDER BY category, name").fetchall()
    return [dict(s) for s in skills]


@app.post("/profile/skills")
async def add_skill_to_profile(body: SkillAddIn, user: Caller = Depends(current_user)):
    if not body.skill_name.strip():
        raise HTTPException(422, "Skill name cannot be empty.")
    try:
        updated = skillswap_ledger.add_user_skill(
            user_id=user.id,
            skill_name=body.skill_name.strip(),
            kind=body.kind,
            level=body.level,
            hourly_rate_credits=body.hourly_rate_credits,
            description=body.description,
        )
        return updated
    except ValueError as ve:
        raise HTTPException(422, str(ve))
    except Exception as e:
        raise HTTPException(500, f"Error saving skill: {str(e)}")


@app.delete("/profile/skills/{user_skill_id}")
async def remove_skill_from_profile(user_skill_id: str, user: Caller = Depends(current_user)):
    try:
        updated = skillswap_ledger.delete_user_skill(user.id, user_skill_id)
        return updated
    except Exception as e:
        raise HTTPException(500, f"Error removing skill: {str(e)}")


# ----------------------------------------------------------------------------
# SPRINT 1: US-04 View Wallet and History (Zero-Sum Invariant)
# ----------------------------------------------------------------------------
@app.get("/wallet/me")
async def get_my_wallet(user: Caller = Depends(current_user)):
    try:
        summary = skillswap_ledger.get_wallet_summary(user.id)
        return summary
    except Exception as e:
        raise HTTPException(500, f"Wallet error: {str(e)}")


@app.get("/wallet/ledger")
async def get_my_ledger(user: Caller = Depends(current_user)):
    try:
        summary = skillswap_ledger.get_wallet_summary(user.id)
        return summary["history"]
    except Exception as e:
        raise HTTPException(500, f"Ledger error: {str(e)}")


@app.get("/wallet/audit")
async def get_ledger_audit(user: Caller = Depends(current_user)):
    report = skillswap_ledger.audit_ledger()
    return report


# ----------------------------------------------------------------------------
# 1. SEARCH  (UC-03 / FR5, FR6)
# ----------------------------------------------------------------------------
def embed(text: str) -> list[float]:
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embedder.encode(text, normalize_embeddings=True).tolist()


class SearchIn(BaseModel):
    goal: str = Field(min_length=1)
    max_rate: Optional[int] = None
    min_rating: float = 0
    limit: int = 20


class SlotCreateIn(BaseModel):
    start_time: str
    end_time: str
    rate_credits: int = Field(default=1, gt=0)
    skill_id: Optional[str] = None


@app.get("/slots/mine")
async def get_my_slots(user: Caller = Depends(current_user)):
    return skillswap_ledger.get_mentor_slots(user.id)


@app.post("/slots")
async def create_availability_slot_endpoint(body: SlotCreateIn, user: Caller = Depends(current_user)):
    try:
        return skillswap_ledger.create_availability_slot(
            mentor_id=user.id,
            start_time=body.start_time,
            end_time=body.end_time,
            rate_credits=body.rate_credits,
            skill_id=body.skill_id,
        )
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    except Exception as e:
        raise HTTPException(500, f"Error creating slot: {str(e)}")


@app.delete("/slots/{slot_id}")
async def cancel_slot_endpoint(slot_id: str, user: Caller = Depends(current_user)):
    try:
        return skillswap_ledger.cancel_availability_slot(user.id, slot_id)
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    except Exception as e:
        raise HTTPException(500, f"Error cancelling slot: {str(e)}")


@app.get("/slots/mentor/{mentor_id}")
async def get_mentor_open_slots(mentor_id: str):
    return skillswap_ledger.get_mentor_slots(mentor_id, status_filter="open")


@app.get("/search/mentors")
async def search_mentors_get(
    q: str = Query(..., description="Learning goal query"),
    max_rate: Optional[int] = Query(None),
    min_rating: float = Query(0.0),
    limit: int = Query(20),
):
    results = skillswap_ledger.search_mentors_by_goal(
        goal=q,
        max_rate=max_rate,
        min_rating=min_rating,
        limit=limit,
    )
    return {"results": results, "suggest_broader": len(results) == 0}


@app.post("/search")
async def search(body: SearchIn, user: Caller = Depends(current_user)):
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(422, "Please enter what you want to learn.")
    if USE_LOCAL_DB:
        results = skillswap_ledger.search_mentors_by_goal(
            goal=goal,
            max_rate=body.max_rate,
            min_rating=body.min_rating,
            limit=body.limit,
        )
        return {"results": results, "suggest_broader": len(results) == 0}
    else:
        vec = await asyncio.to_thread(embed, goal)
        results = await rpc("match_mentors", {
            "query_embedding": vec, "max_rate": body.max_rate,
            "min_rating": body.min_rating, "match_count": body.limit,
        }, token=user.token)
        return {"results": results, "suggest_broader": len(results) == 0}


@app.get("/mentors/{mentor_id}")
async def get_mentor_profile(mentor_id: str):
    try:
        return skillswap_ledger.get_mentor_public_profile(mentor_id)
    except ValueError as ve:
        raise HTTPException(404, str(ve))
    except Exception as e:
        raise HTTPException(500, f"Error fetching mentor profile: {str(e)}")


@app.get("/mentors/{mentor_id}/slots")
async def mentor_slots(mentor_id: str):
    if USE_LOCAL_DB:
        return skillswap_ledger.get_mentor_slots(mentor_id, status_filter="open")
    return await select("availability_slots", {
        "mentor_id": f"eq.{mentor_id}", "status": "eq.open",
        "start_time": f"gt.{datetime.now(timezone.utc).isoformat()}",
        "order": "start_time.asc", "select": "*",
    })


# ----------------------------------------------------------------------------
# 2. BOOKING  (UC-04 / FR8-FR12, FR17)  Redis mutex  ->  book_slot() ACID RPC
# ----------------------------------------------------------------------------
RELEASE_LUA = "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"


class BookingIn(BaseModel):
    slot_id: str
    objectives: Optional[str] = None


@app.post("/booking", status_code=201)
async def book(body: BookingIn, user: Caller = Depends(current_user)):
    lock_key, lock_val = f"lock:slot:{body.slot_id}", str(uuid.uuid4())
    if not await redis.set(lock_key, lock_val, nx=True, ex=LOCK_TTL_SECONDS):
        raise HTTPException(409, "This slot is no longer available.")        # A1 slot collision
    try:
        booking_id = await rpc("book_slot", {"p_slot_id": body.slot_id, "p_objectives": body.objectives},
                               token=user.token)
        try:
            await provision_room(booking_id)
        except Exception:
            # QR10 / UC-06 E1: room could not be created -> refund escrow, release slot
            await rpc("refund_booking", {"p_booking_id": booking_id, "p_strike_mentor": False}, service=True)
            raise HTTPException(502, "Could not create the session room. You were not charged.")
        return {"booking_id": booking_id, "status": "confirmed"}
    finally:
        await redis.eval(RELEASE_LUA, 1, lock_key, lock_val)


async def provision_room(booking_id: str):
    b = (await select("bookings", {"id": f"eq.{booking_id}", "select": "scheduled_end"}, service=True))[0]
    end = datetime.fromisoformat(b["scheduled_end"].replace("Z", "+00:00"))
    await insert("session_rooms", {
        "booking_id": booking_id, "room_name": f"skillswap-{uuid.uuid4().hex[:16]}",
        "jitsi_domain": JITSI_DOMAIN, "expires_at": (end + ROOM_AFTER_END).isoformat(),
    }, service=True)
    await insert("session_events", {"booking_id": booking_id, "event_type": "room_created"}, service=True)


@app.get("/bookings/{booking_id}/ics", response_class=PlainTextResponse)
async def booking_ics(booking_id: str, user: Caller = Depends(current_user)):
    rows = await select("bookings", {"id": f"eq.{booking_id}", "select": "*"}, token=user.token)  # RLS: participants only
    if not rows:
        raise HTTPException(404, "Booking not found")
    b = rows[0]
    fmt = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%Y%m%dT%H%M%SZ")
    ics = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SkillSwap//EN", "BEGIN:VEVENT",
        f"UID:{b['id']}@skillswap", f"DTSTAMP:{fmt(datetime.now(timezone.utc).isoformat())}",
        f"DTSTART:{fmt(b['scheduled_start'])}", f"DTEND:{fmt(b['scheduled_end'])}",
        "SUMMARY:SkillSwap session", f"DESCRIPTION:{b.get('objectives') or ''}",
        "BEGIN:VALARM", "TRIGGER:-PT15M", "ACTION:DISPLAY", "DESCRIPTION:Session starts soon", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR",
    ])
    return PlainTextResponse(ics, media_type="text/calendar")


# ----------------------------------------------------------------------------
# 3. SESSION  (UC-06 / FR13, FR23)  join token + heartbeats
# ----------------------------------------------------------------------------
async def get_booking_for(user: Caller, booking_id: str) -> dict:
    rows = await select("bookings", {"id": f"eq.{booking_id}", "select": "*"}, token=user.token)
    if not rows or user.id not in (rows[0]["learner_id"], rows[0]["mentor_id"]):
        raise HTTPException(403, "You are not part of this booking.")
    return rows[0]


@app.post("/bookings/{booking_id}/join")
async def join_session(booking_id: str, user: Caller = Depends(current_user)):
    b = await get_booking_for(user, booking_id)
    if b["escrow_status"] != "held":
        raise HTTPException(409, "This session is no longer active.")
    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(b["scheduled_start"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(b["scheduled_end"].replace("Z", "+00:00"))
    if now < start - JOIN_EARLY:
        raise HTTPException(425, "The room opens 10 minutes before the session.")
    if now > end + ROOM_AFTER_END:
        raise HTTPException(410, "This session room has expired.")

    room = (await select("session_rooms", {"booking_id": f"eq.{booking_id}", "select": "*"}, service=True))[0]
    exp = int((end + ROOM_AFTER_END).timestamp())                      # QR13: expires after scheduled end
    jti = str(uuid.uuid4())
    prof = (await select("profiles", {"id": f"eq.{user.id}", "select": "full_name"}, service=True))[0]
    token = jwt.encode({
        "aud": "jitsi", "iss": JITSI_APP_ID, "sub": JITSI_DOMAIN, "room": room["room_name"],
        "exp": exp, "nbf": int(time.time()) - 10, "jti": jti,
        "context": {"user": {"id": user.id, "name": prof["full_name"],
                             "moderator": user.id == b["mentor_id"]}},
    }, JITSI_APP_SECRET, algorithm="HS256")

    await insert("session_tokens", {"jti": jti, "booking_id": booking_id, "user_id": user.id,
                                    "expires_at": datetime.fromtimestamp(exp, timezone.utc).isoformat()}, service=True)
    await insert("session_events", {"booking_id": booking_id, "user_id": user.id, "event_type": "joined"}, service=True)
    await redis.set(f"hb:{booking_id}:{user.id}", "1", ex=HEARTBEAT_TTL_SECONDS)
    if b["status"] == "confirmed":
        await patch("bookings", {"id": f"eq.{booking_id}"}, {"status": "in_progress"}, service=True)
    return {"domain": JITSI_DOMAIN, "room": room["room_name"], "jwt": token}


@app.post("/bookings/{booking_id}/heartbeat")
async def heartbeat(booking_id: str, user: Caller = Depends(current_user)):
    """Frontend calls this every ~10s while in the room."""
    await get_booking_for(user, booking_id)
    key = f"hb:{booking_id}:{user.id}"
    was_alive = await redis.exists(key)
    await redis.set(key, "1", ex=HEARTBEAT_TTL_SECONDS)
    if not was_alive:   # connection resumed after a drop (A3 brief drop)
        await insert("session_events", {"booking_id": booking_id, "user_id": user.id,
                                        "event_type": "heartbeat_resumed"}, service=True)
    return {"ok": True}


@app.get("/bookings/{booking_id}/presence")
async def presence(booking_id: str, user: Caller = Depends(current_user)):
    b = await get_booking_for(user, booking_id)
    other = b["mentor_id"] if user.id == b["learner_id"] else b["learner_id"]
    return {"other_online": bool(await redis.exists(f"hb:{booking_id}:{other}"))}


# ----------------------------------------------------------------------------
# 4. SETTLEMENT, DISPUTES  (FR24, FR15, FR26)
# ----------------------------------------------------------------------------
@app.post("/bookings/{booking_id}/sign-off")
async def sign_off(booking_id: str, user: Caller = Depends(current_user)):
    result = await rpc("sign_off_booking", {"p_booking_id": booking_id}, token=user.token)
    if result == "settled":
        await rpc("audit_ledger", {"p_auto": True}, service=True)      # FR28 zero-sum audit after every settlement
    return {"result": result}


class DisputeIn(BaseModel):
    reason: str   # mentor_no_show | poor_quality | learner_misconduct | technical_issue | other
    details: Optional[str] = None


@app.post("/bookings/{booking_id}/dispute", status_code=201)
async def raise_dispute(booking_id: str, body: DisputeIn, user: Caller = Depends(current_user)):
    dispute_id = await rpc("raise_dispute", {"p_booking_id": booking_id, "p_reason": body.reason,
                                             "p_details": body.details}, token=user.token)
    return {"dispute_id": dispute_id, "status": "open"}


@app.post("/disputes/{dispute_id}/withdraw")
async def withdraw_dispute(dispute_id: str, user: Caller = Depends(current_user)):      # UC-07 A1
    rows = await select("disputes", {"id": f"eq.{dispute_id}", "select": "*"}, service=True)
    if not rows or rows[0]["raised_by"] != user.id:
        raise HTTPException(403, "Only the person who raised the dispute can withdraw it.")
    if rows[0]["status"] not in ("open", "info_requested"):
        raise HTTPException(409, "This dispute can no longer be withdrawn.")
    await patch("disputes", {"id": f"eq.{dispute_id}"}, {"status": "withdrawn",
                                                         "resolved_at": datetime.now(timezone.utc).isoformat()}, service=True)
    await patch("bookings", {"id": f"eq.{rows[0]['booking_id']}"},
                {"status": "in_progress", "escrow_status": "held"}, service=True)    # unfreeze, settlement continues
    return {"status": "withdrawn"}


# ----------------------------------------------------------------------------
# 5. ADMIN  (UC-08, UC-09 / FR30-FR32)
# ----------------------------------------------------------------------------
@app.get("/admin/disputes")
async def admin_disputes(status: str = "open", admin: Caller = Depends(require_admin)):
    return await select("disputes", {
        "status": f"eq.{status}", "order": "created_at.asc",
        "select": "*,booking:bookings(*,learner:profiles!bookings_learner_id_fkey(full_name,strike_count),"
                  "mentor:profiles!bookings_mentor_id_fkey(full_name,strike_count))",
    }, service=True)


class ResolveIn(BaseModel):
    outcome: str                      # refund_learner | pay_mentor | split
    learner_share: Optional[int] = None
    notes: Optional[str] = None
    strike_mentor: bool = False


@app.post("/admin/disputes/{dispute_id}/resolve")
async def admin_resolve(dispute_id: str, body: ResolveIn, admin: Caller = Depends(require_admin)):
    await rpc("resolve_dispute", {
        "p_dispute_id": dispute_id, "p_outcome": body.outcome, "p_learner_share": body.learner_share,
        "p_notes": body.notes, "p_strike_mentor": body.strike_mentor,
    }, token=admin.token)
    await rpc("audit_ledger", {"p_auto": True}, service=True)
    return {"status": "resolved"}


class MoreInfoIn(BaseModel):
    message: str


@app.post("/admin/disputes/{dispute_id}/request-info")
async def admin_request_info(dispute_id: str, body: MoreInfoIn, admin: Caller = Depends(require_admin)):   # A1
    d = (await patch("disputes", {"id": f"eq.{dispute_id}"}, {"status": "info_requested"}, service=True))[0]
    b = (await select("bookings", {"id": f"eq.{d['booking_id']}", "select": "learner_id,mentor_id"}, service=True))[0]
    for uid in (b["learner_id"], b["mentor_id"]):
        await insert("notifications", {"user_id": uid, "type": "dispute_update",
                                       "title": "Admin needs more information", "body": body.message}, service=True)
    return {"status": "info_requested"}


@app.post("/admin/audit")
async def admin_audit(admin: Caller = Depends(require_admin)):
    return await rpc("audit_ledger", {"p_auto": False}, token=admin.token)


@app.get("/admin/audits")
async def admin_audits(admin: Caller = Depends(require_admin)):
    return await select("audit_reports", {"order": "created_at.desc", "limit": "50"}, service=True)


class SuspendIn(BaseModel):
    reason: str


@app.post("/admin/users/{user_id}/suspend")
async def admin_suspend(user_id: str, body: SuspendIn, admin: Caller = Depends(require_admin)):
    await patch("profiles", {"id": f"eq.{user_id}"}, {"status": "suspended", "suspension_reason": body.reason}, service=True)
    return {"status": "suspended"}


@app.post("/admin/users/{user_id}/reinstate")
async def admin_reinstate(user_id: str, admin: Caller = Depends(require_admin)):
    await patch("profiles", {"id": f"eq.{user_id}"}, {"status": "active", "suspension_reason": None}, service=True)
    return {"status": "active"}


# ----------------------------------------------------------------------------
# 6. NO-SHOW SWEEPER  (FR25)  runs every 30s in the background
#    Replace with a cron/worker (e.g. Render cron, Supabase pg_cron + Edge Function) if you run >1 API instance.
# ----------------------------------------------------------------------------
async def no_show_sweeper():
    while True:
        try:
            await sweep_no_shows()
        except asyncio.CancelledError:
            raise
        except Exception as e:           # never let the loop die
            print("sweeper error:", e)
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)


async def sweep_no_shows():
    now = datetime.now(timezone.utc).isoformat()
    overdue = await select("bookings", {
        "status": "eq.confirmed", "escrow_status": "eq.held",
        "grace_deadline": f"lt.{now}", "select": "id,learner_id,mentor_id",
    }, service=True)
    for b in overdue:
        # one sweeper at a time per booking
        if not await redis.set(f"sweep:{b['id']}", "1", nx=True, ex=60):
            continue
        joined = {e["user_id"] for e in await select("session_events", {
            "booking_id": f"eq.{b['id']}", "event_type": "eq.joined", "select": "user_id"}, service=True)}
        mentor_in, learner_in = b["mentor_id"] in joined, b["learner_id"] in joined
        if not mentor_in:
            # mentor absent (alone or with learner absent too): refund learner, strike only if the learner showed up
            await rpc("refund_booking", {"p_booking_id": b["id"], "p_strike_mentor": learner_in}, service=True)
        elif not learner_in:
            # learner absent: flag both sides; mentor can raise a dispute / admin decides (SRS: "flags an absent learner")
            for uid, text in ((b["learner_id"], "You missed your session."),
                              (b["mentor_id"], "The learner did not join. You can raise a dispute.")):
                await insert("notifications", {"user_id": uid, "type": "no_show", "title": text,
                                               "data": {"booking_id": b["id"]}}, service=True)
            await patch("bookings", {"id": f"eq.{b['id']}"}, {"status": "in_progress"}, service=True)


@app.get("/health")
async def health():
    return {"ok": True}
