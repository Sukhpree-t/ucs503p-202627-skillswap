"""
SkillSwap Zero-Sum Double-Entry Ledger and Account Engine
Enforces Working Agreement #5:
- The client never computes or trusts balances.
- All credit movement goes through SQL / transactional RPC functions.
- The ledger is zero-sum: SUM(accounts.balance) = 0.
"""
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

DEFAULT_DB_PATH = os.environ.get("SKILLSWAP_DB_PATH", "skillswap.db")
DEFAULT_STARTER_CREDITS = int(os.environ.get("SKILLSWAP_STARTER_CREDITS", "3"))


class AccountSuspendedError(Exception):
    def __init__(self, reason: str = "Account suspended by administrator"):
        super().__init__(reason)
        self.reason = reason


class SSOUnavailableError(Exception):
    def __init__(self, message: str = "Campus SSO Identity Provider is currently unreachable"):
        super().__init__(message)
        self.message = message


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH):
    """Initializes tables and seeds mint/escrow accounts matching skillswap_schema.sql"""
    conn = get_connection(db_path)
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            campus_email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            avatar_url TEXT,
            department TEXT,
            study_year INTEGER CHECK (study_year BETWEEN 1 AND 6),
            bio TEXT,
            role TEXT NOT NULL DEFAULT 'peer' CHECK (role IN ('peer', 'admin')),
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
            suspension_reason TEXT,
            strike_count INTEGER NOT NULL DEFAULT 0,
            quiz_completed INTEGER NOT NULL DEFAULT 0,
            mentor_rating_avg REAL NOT NULL DEFAULT 0.0,
            mentor_rating_count INTEGER NOT NULL DEFAULT 0,
            learner_rating_avg REAL NOT NULL DEFAULT 0.0,
            learner_rating_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            category TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_skills (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK (kind IN ('offered', 'desired')),
            level TEXT NOT NULL CHECK (level IN ('beginner', 'intermediate', 'advanced')),
            description TEXT,
            hourly_rate_credits INTEGER CHECK (hourly_rate_credits IS NULL OR hourly_rate_credits > 0),
            quiz_score REAL,
            embedding_stale INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            UNIQUE (user_id, skill_id, kind)
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL CHECK (kind IN ('user', 'escrow', 'mint')),
            owner_id TEXT UNIQUE REFERENCES profiles(id) ON DELETE RESTRICT,
            balance INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            CHECK (kind = 'mint' OR balance >= 0),
            CHECK ((kind = 'user' AND owner_id IS NOT NULL) OR (kind <> 'user' AND owner_id IS NULL))
        );

        CREATE TABLE IF NOT EXISTS ledger_transactions (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL CHECK (type IN (
                'starter_grant', 'escrow_lock', 'settlement', 'refund',
                'dispute_refund', 'dispute_payout', 'dispute_split'
            )),
            booking_id TEXT,
            description TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ledger_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL REFERENCES ledger_transactions(id) ON DELETE RESTRICT,
            account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
            direction TEXT NOT NULL CHECK (direction IN ('debit', 'credit')),
            amount INTEGER NOT NULL CHECK (amount > 0),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_reports (
            id TEXT PRIMARY KEY,
            run_by TEXT REFERENCES profiles(id),
            passed INTEGER NOT NULL,
            total_debits INTEGER NOT NULL,
            total_credits INTEGER NOT NULL,
            total_issued INTEGER NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS availability_slots (
            id TEXT PRIMARY KEY,
            mentor_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            skill_id TEXT REFERENCES skills(id),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            rate_credits INTEGER NOT NULL CHECK (rate_credits > 0),
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'booked', 'cancelled')),
            external_event_id TEXT,
            created_at TEXT NOT NULL,
            CHECK (end_time > start_time)
        );
        """)

        now = datetime.now(timezone.utc).isoformat()

        # Seed configuration table
        conn.execute(
            "INSERT OR REPLACE INTO app_config (key, value, description, updated_at) VALUES ('starter_credits', ?, 'Number of starter credits granted on student registration', ?)",
            (str(DEFAULT_STARTER_CREDITS), now),
        )

        # Safe schema migration for existing databases
        cursor = conn.cursor()
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(user_skills)").fetchall()]
        if cols and "embedding_stale" not in cols:
            conn.execute("ALTER TABLE user_skills ADD COLUMN embedding_stale INTEGER NOT NULL DEFAULT 1")

        pcols = [r[1] for r in cursor.execute("PRAGMA table_info(profiles)").fetchall()]
        if pcols and "status" not in pcols:
            conn.execute("ALTER TABLE profiles ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        if pcols and "suspension_reason" not in pcols:
            conn.execute("ALTER TABLE profiles ADD COLUMN suspension_reason TEXT")

        # Seed system accounts: mint and escrow
        mint_row = conn.execute("SELECT id FROM accounts WHERE kind = 'mint'").fetchone()
        if not mint_row:
            conn.execute(
                "INSERT INTO accounts (id, kind, owner_id, balance, created_at) VALUES (?, 'mint', NULL, 0, ?)",
                (str(uuid.uuid4()), now),
            )

        escrow_row = conn.execute("SELECT id FROM accounts WHERE kind = 'escrow'").fetchone()
        if not escrow_row:
            conn.execute(
                "INSERT INTO accounts (id, kind, owner_id, balance, created_at) VALUES (?, 'escrow', NULL, 0, ?)",
                (str(uuid.uuid4()), now),
            )

        # Seed initial skills catalog
        sample_skills = [
            ("Python & Backend", "python-backend", "Engineering"),
            ("Data Structures & Algorithms", "dsa", "Computer Science"),
            ("React & Frontend", "react-frontend", "Web Development"),
            ("Machine Learning & AI", "machine-learning", "Data Science"),
            ("System Design", "system-design", "Architecture"),
            ("UI/UX Design & Figma", "ui-ux", "Design"),
            ("SQL & Database Engineering", "sql-databases", "Data Engineering"),
            ("Cloud & DevOps", "devops-cloud", "Infrastructure"),
        ]
        for name, slug, cat in sample_skills:
            conn.execute(
                "INSERT OR IGNORE INTO skills (id, name, slug, category, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), name, slug, cat, now),
            )


class LedgerError(Exception):
    pass


class InsufficientBalanceError(LedgerError):
    pass


def post_transfer(
    from_acc_id: str,
    to_acc_id: str,
    amount: int,
    tx_type: str,
    booking_id: Optional[str] = None,
    description: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
    conn: Optional[sqlite3.Connection] = None,
) -> str:
    """
    Atomically moves credits from from_acc_id to to_acc_id.
    Enforces double-entry balance and non-negative constraints.
    Returns transaction_id.
    """
    if amount <= 0:
        raise LedgerError("Transfer amount must be strictly greater than 0.")

    close_conn = False
    if conn is None:
        conn = get_connection(db_path)
        close_conn = True

    try:
        with conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()

            # Check from_account
            from_acc = cursor.execute("SELECT id, kind, balance FROM accounts WHERE id = ?", (from_acc_id,)).fetchone()
            if not from_acc:
                raise LedgerError(f"Source account {from_acc_id} does not exist.")

            to_acc = cursor.execute("SELECT id, kind, balance FROM accounts WHERE id = ?", (to_acc_id,)).fetchone()
            if not to_acc:
                raise LedgerError(f"Destination account {to_acc_id} does not exist.")

            # Mint account can go negative; all other accounts must have sufficient balance
            if from_acc["kind"] != "mint" and from_acc["balance"] < amount:
                raise InsufficientBalanceError(
                    f"Insufficient balance. Available: {from_acc['balance']}, Required: {amount}."
                )

            tx_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO ledger_transactions (id, type, booking_id, description, created_at) VALUES (?, ?, ?, ?, ?)",
                (tx_id, tx_type, booking_id, description, now),
            )

            # Double entry: 1 debit from source, 1 credit to destination
            cursor.execute(
                "INSERT INTO ledger_entries (transaction_id, account_id, direction, amount, created_at) VALUES (?, ?, 'debit', ?, ?)",
                (tx_id, from_acc_id, amount, now),
            )
            cursor.execute(
                "INSERT INTO ledger_entries (transaction_id, account_id, direction, amount, created_at) VALUES (?, ?, 'credit', ?, ?)",
                (tx_id, to_acc_id, amount, now),
            )

            # Update balances
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_acc_id))
            cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_acc_id))

            # Enforce zero-sum invariant check
            sum_row = cursor.execute("SELECT SUM(balance) as total FROM accounts").fetchone()
            if sum_row and sum_row["total"] != 0:
                raise LedgerError(f"ZERO-SUM INVARIANT VIOLATION: SUM(accounts.balance) = {sum_row['total']}")

        return tx_id
    finally:
        if close_conn:
            conn.close()


def register_or_login_campus_user(
    campus_email: str,
    full_name: str,
    avatar_url: Optional[str] = None,
    department: Optional[str] = "Computer Science",
    study_year: int = 3,
    starter_credits: int = 3,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict:
    """
    US-01: Campus SSO user lookup/creation.
    If new user: creates profile, user account, and mints starter credits via double-entry transaction.
    """
    campus_email = campus_email.strip().lower()
    if not campus_email:
        raise ValueError("Campus email is required.")
    if not full_name.strip():
        raise ValueError("Full name is required.")

    conn = get_connection(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            cursor = conn.cursor()
            profile = cursor.execute("SELECT * FROM profiles WHERE campus_email = ?", (campus_email,)).fetchone()
            if profile and profile["status"] == "suspended":
                reason = profile["suspension_reason"] or "Account suspended by campus administrator"
                raise AccountSuspendedError(reason)

            if not profile:
                user_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO profiles (id, campus_email, full_name, avatar_url, department, study_year, bio, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        campus_email,
                        full_name.strip(),
                        avatar_url or f"https://api.dicebear.com/7.x/bottts/svg?seed={campus_email}",
                        department,
                        study_year,
                        "Peer learner and mentor eager to exchange skills.",
                        now,
                        now,
                    ),
                )
                # Create user account
                acc_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO accounts (id, kind, owner_id, balance, created_at) VALUES (?, 'user', ?, 0, ?)",
                    (acc_id, user_id, now),
                )
                # Mint starter credits from MINT to USER account using app_config single source of truth
                cfg_row = cursor.execute("SELECT value FROM app_config WHERE key = 'starter_credits'").fetchone()
                effective_starter = int(cfg_row["value"]) if cfg_row else starter_credits

                mint_acc = cursor.execute("SELECT id FROM accounts WHERE kind = 'mint'").fetchone()
                if not mint_acc:
                    raise LedgerError("Mint account not found.")

                # Call double-entry transfer
                post_transfer(
                    from_acc_id=mint_acc["id"],
                    to_acc_id=acc_id,
                    amount=effective_starter,
                    tx_type="starter_grant",
                    description="Welcome starter credits grant",
                    db_path=db_path,
                    conn=conn,
                )

            profile = cursor.execute("SELECT * FROM profiles WHERE campus_email = ?", (campus_email,)).fetchone()
            acc = cursor.execute("SELECT * FROM accounts WHERE owner_id = ?", (profile["id"],)).fetchone()
            return {
                "id": profile["id"],
                "campus_email": profile["campus_email"],
                "full_name": profile["full_name"],
                "avatar_url": profile["avatar_url"],
                "department": profile["department"],
                "study_year": profile["study_year"],
                "bio": profile["bio"],
                "role": profile["role"],
                "balance": acc["balance"] if acc else 0,
            }
    finally:
        conn.close()


def get_wallet_summary(user_id: str, db_path: str = DEFAULT_DB_PATH) -> Dict:
    """
    US-04: Returns Available Balance, Escrow Balance, and Double-entry Ledger History.
    Client never calculates balance; derived strictly from DB accounts.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            acc = conn.execute("SELECT id, balance FROM accounts WHERE owner_id = ?", (user_id,)).fetchone()
            if not acc:
                raise LedgerError(f"No account found for user {user_id}")

            user_acc_id = acc["id"]
            available_balance = acc["balance"]
            escrow_balance = 0

            transactions_rows = conn.execute(
                """
                SELECT 
                    lt.id as transaction_id,
                    lt.type,
                    lt.description,
                    lt.created_at,
                    le.direction,
                    le.amount
                FROM ledger_entries le
                JOIN ledger_transactions lt ON le.transaction_id = lt.id
                WHERE le.account_id = ?
                ORDER BY lt.created_at DESC, le.id DESC
                """,
                (user_acc_id,),
            ).fetchall()

            history = [
                {
                    "transaction_id": row["transaction_id"],
                    "type": row["type"],
                    "description": row["description"] or row["type"].replace("_", " ").title(),
                    "created_at": row["created_at"],
                    "direction": row["direction"],
                    "amount": row["amount"],
                    "delta": row["amount"] if row["direction"] == "credit" else -row["amount"],
                }
                for row in transactions_rows
            ]

            return {
                "account_id": user_acc_id,
                "available_balance": available_balance,
                "escrow_balance": escrow_balance,
                "total_balance": available_balance + escrow_balance,
                "history": history,
            }
    finally:
        conn.close()


def get_profile_data(user_id: str, db_path: str = DEFAULT_DB_PATH) -> Dict:
    """
    US-02: Returns user profile and categorized skills (offered vs desired).
    """
    conn = get_connection(db_path)
    try:
        with conn:
            profile = conn.execute("SELECT * FROM profiles WHERE id = ?", (user_id,)).fetchone()
            if not profile:
                raise ValueError("Profile not found")

            acc = conn.execute("SELECT balance FROM accounts WHERE owner_id = ?", (user_id,)).fetchone()

            user_skills_rows = conn.execute(
                """
                SELECT 
                    us.id,
                    us.kind,
                    us.level,
                    us.description,
                    us.hourly_rate_credits,
                    us.embedding_stale,
                    s.id as skill_id,
                    s.name as skill_name,
                    s.slug as skill_slug,
                    s.category as skill_category
                FROM user_skills us
                JOIN skills s ON us.skill_id = s.id
                WHERE us.user_id = ?
                ORDER BY us.created_at ASC
                """,
                (user_id,),
            ).fetchall()

            offered = []
            desired = []
            for r in user_skills_rows:
                item = {
                    "id": r["id"],
                    "skill_id": r["skill_id"],
                    "name": r["skill_name"],
                    "slug": r["skill_slug"],
                    "category": r["skill_category"],
                    "level": r["level"],
                    "description": r["description"],
                    "hourly_rate_credits": r["hourly_rate_credits"],
                    "embedding_stale": bool(r["embedding_stale"]) if "embedding_stale" in r.keys() else True,
                }
                if r["kind"] == "offered":
                    offered.append(item)
                else:
                    desired.append(item)

            return {
                "id": profile["id"],
                "campus_email": profile["campus_email"],
                "full_name": profile["full_name"],
                "avatar_url": profile["avatar_url"],
                "department": profile["department"],
                "study_year": profile["study_year"],
                "bio": profile["bio"],
                "role": profile["role"],
                "status": profile["status"],
                "mentor_rating_avg": profile["mentor_rating_avg"],
                "mentor_rating_count": profile["mentor_rating_count"],
                "learner_rating_avg": profile["learner_rating_avg"],
                "learner_rating_count": profile["learner_rating_count"],
                "balance": acc["balance"] if acc else 0,
                "offered_skills": offered,
                "desired_skills": desired,
            }
    finally:
        conn.close()


def update_profile(user_id: str, bio: Optional[str], department: Optional[str], study_year: Optional[int], db_path: str = DEFAULT_DB_PATH) -> Dict:
    conn = get_connection(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute(
                """
                UPDATE profiles
                SET bio = COALESCE(?, bio),
                    department = COALESCE(?, department),
                    study_year = COALESCE(?, study_year),
                    updated_at = ?
                WHERE id = ?
                """,
                (bio, department, study_year, now, user_id),
            )
        return get_profile_data(user_id, db_path=db_path)
    finally:
        conn.close()


def add_user_skill(
    user_id: str,
    skill_name: str,
    kind: str,
    level: str,
    hourly_rate_credits: Optional[int] = 1,
    description: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict:
    """Adds a skill to user profile, creating the skill in catalog if not present."""
    if not skill_name.strip():
        raise ValueError("Skill name cannot be empty.")
    if kind not in ("offered", "desired"):
        raise ValueError("Kind must be 'offered' or 'desired'.")
    if level not in ("beginner", "intermediate", "advanced"):
        raise ValueError("Level must be 'beginner', 'intermediate', or 'advanced'.")

    conn = get_connection(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            cursor = conn.cursor()
            slug = skill_name.strip().lower().replace(" ", "-").replace("&", "and")
            skill_row = cursor.execute("SELECT id FROM skills WHERE slug = ? OR name = ?", (slug, skill_name.strip())).fetchone()
            if skill_row:
                skill_id = skill_row["id"]
            else:
                skill_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO skills (id, name, slug, category, created_at) VALUES (?, ?, ?, 'Peer Catalog', ?)",
                    (skill_id, skill_name.strip(), slug, now),
                )

            # Check existing
            existing = cursor.execute(
                "SELECT id FROM user_skills WHERE user_id = ? AND skill_id = ? AND kind = ?",
                (user_id, skill_id, kind),
            ).fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE user_skills 
                    SET level = ?, description = ?, hourly_rate_credits = ?, embedding_stale = 1
                    WHERE id = ?
                    """,
                    (level, description, hourly_rate_credits if kind == "offered" else None, existing["id"]),
                )
            else:
                item_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO user_skills (id, user_id, skill_id, kind, level, description, hourly_rate_credits, embedding_stale, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        item_id,
                        user_id,
                        skill_id,
                        kind,
                        level,
                        description,
                        hourly_rate_credits if kind == "offered" else None,
                        now,
                    ),
                )

        return get_profile_data(user_id, db_path=db_path)
    finally:
        conn.close()


def delete_user_skill(user_id: str, user_skill_id: str, db_path: str = DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM user_skills WHERE id = ? AND user_id = ?", (user_skill_id, user_id))
        return get_profile_data(user_id, db_path=db_path)
    finally:
        conn.close()


def create_availability_slot(
    mentor_id: str,
    start_time: str,
    end_time: str,
    rate_credits: int,
    skill_id: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict:
    """
    US-08: Publishes an availability slot for a mentor with hourly rate credits.
    Enforces:
    - end_time > start_time
    - start_time >= now (no slots in the past)
    - rate_credits > 0
    - No overlapping active (status != 'cancelled') slots for the same mentor
    """
    if rate_credits <= 0:
        raise ValueError("Rate credits must be greater than 0.")

    # Parse and validate ISO timestamps
    try:
        dt_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        dt_end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except Exception as e:
        raise ValueError(f"Invalid timestamp format: {e}")

    if dt_end <= dt_start:
        raise ValueError("End time must be after start time.")

    now_utc = datetime.now(timezone.utc)
    if dt_start < now_utc:
        raise ValueError("Cannot create availability slots in the past.")

    start_iso = dt_start.isoformat()
    end_iso = dt_end.isoformat()
    if not skill_id or not str(skill_id).strip():
        skill_id = None

    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            # Verify mentor exists
            mentor = cursor.execute("SELECT id FROM profiles WHERE id = ?", (mentor_id,)).fetchone()
            if not mentor:
                raise ValueError("Mentor profile not found.")

            # Overlap check: An overlap occurs when new_start < existing_end AND new_end > existing_start
            overlap = cursor.execute(
                """
                SELECT id, start_time, end_time FROM availability_slots
                WHERE mentor_id = ?
                  AND status != 'cancelled'
                  AND (? < end_time AND ? > start_time)
                LIMIT 1
                """,
                (mentor_id, start_iso, end_iso),
            ).fetchone()

            if overlap:
                raise ValueError(
                    f"Slot overlaps with an existing slot ({overlap['start_time']} to {overlap['end_time']})."
                )

            slot_id = str(uuid.uuid4())
            created_now = now_utc.isoformat()
            cursor.execute(
                """
                INSERT INTO availability_slots (id, mentor_id, skill_id, start_time, end_time, rate_credits, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (slot_id, mentor_id, skill_id, start_iso, end_iso, rate_credits, created_now),
            )

            row = cursor.execute("SELECT * FROM availability_slots WHERE id = ?", (slot_id,)).fetchone()
            return dict(row)
    finally:
        conn.close()


def get_mentor_slots(
    mentor_id: str,
    status_filter: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> List[Dict]:
    """
    US-08 / US-07: Returns slots for a mentor ordered by start_time.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            query = "SELECT s.*, sk.name as skill_name FROM availability_slots s LEFT JOIN skills sk ON s.skill_id = sk.id WHERE s.mentor_id = ?"
            params = [mentor_id]
            if status_filter:
                query += " AND s.status = ?"
                params.append(status_filter)
            query += " ORDER BY s.start_time ASC"

            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


def cancel_availability_slot(
    mentor_id: str,
    slot_id: str,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict:
    """
    US-08: Cancels or removes an open slot owned by the mentor.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            slot = cursor.execute("SELECT * FROM availability_slots WHERE id = ? AND mentor_id = ?", (slot_id, mentor_id)).fetchone()
            if not slot:
                raise ValueError("Slot not found or unauthorized.")
            if slot["status"] == "booked":
                raise ValueError("Cannot cancel an already booked slot without settlement/refund.")

            cursor.execute("UPDATE availability_slots SET status = 'cancelled' WHERE id = ?", (slot_id,))
            updated = cursor.execute("SELECT * FROM availability_slots WHERE id = ?", (slot_id,)).fetchone()
            return dict(updated)
    finally:
        conn.close()


def compute_deterministic_embedding(text: str, dim: int = 384) -> List[float]:
    """
    Computes a deterministic 384-dimensional normalized vector for text.
    Uses word n-grams with hashing and semantic synonym expansion.
    Produces standard unit vectors compatible with vector(384) cosine similarity.
    """
    import math
    import hashlib
    import re

    vec = [0.0] * dim
    clean_text = text.lower()

    # Semantic synonym expansion for university skill concepts
    synonyms = {
        "dsa": ["data", "structures", "algorithms", "problem", "solving"],
        "ai": ["machine", "learning", "artificial", "intelligence", "neural"],
        "ml": ["machine", "learning", "data", "science"],
        "web": ["frontend", "backend", "fullstack", "react", "nextjs"],
        "ui": ["design", "figma", "ux", "interface"],
        "cloud": ["devops", "docker", "kubernetes", "aws", "gcp"],
        "sql": ["database", "postgres", "queries", "engineering"],
    }
    words = re.findall(r"\b[a-zA-Z0-9_+#]+\b", clean_text)
    expanded_words = list(words)
    for w in words:
        if w in synonyms:
            expanded_words.extend(synonyms[w])

    if not expanded_words:
        return vec

    # Unigrams and bigrams
    tokens = list(expanded_words)
    for i in range(len(expanded_words) - 1):
        tokens.append(f"{expanded_words[i]}_{expanded_words[i+1]}")

    for token in tokens:
        # Stable 32-bit hash
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) == 0 else -1.0
        vec[idx] += sign

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two unit vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    return max(0.0, min(1.0, dot))


def search_mentors_by_goal(
    goal: str,
    max_rate: Optional[int] = None,
    min_rating: float = 0.0,
    limit: int = 20,
    min_similarity: float = 0.15,
    db_path: str = DEFAULT_DB_PATH,
) -> List[Dict]:
    """
    US-05: Semantic search for mentors by learning goal.
    Scores each mentor based on cosine similarity of the goal to their offered skills and bio.
    Filters by max_rate and min_rating, and provides next available slot preview.
    """
    if not goal.strip():
        return []

    goal_vec = compute_deterministic_embedding(goal)
    conn = get_connection(db_path)
    try:
        with conn:
            # Query all active mentors who offer at least one skill
            mentors = conn.execute(
                """
                SELECT DISTINCT
                    p.id,
                    p.full_name,
                    p.avatar_url,
                    p.department,
                    p.study_year,
                    p.bio,
                    p.mentor_rating_avg,
                    p.mentor_rating_count
                FROM profiles p
                JOIN user_skills us ON us.user_id = p.id AND us.kind = 'offered'
                WHERE p.status = 'active'
                  AND p.mentor_rating_avg >= ?
                """,
                (min_rating,),
            ).fetchall()

            now_iso = datetime.now(timezone.utc).isoformat()
            results = []

            for m in mentors:
                # Get offered skills for this mentor
                skills = conn.execute(
                    """
                    SELECT us.id, us.level, us.description, us.hourly_rate_credits, s.id as skill_id, s.name as skill_name, s.category
                    FROM user_skills us
                    JOIN skills s ON us.skill_id = s.id
                    WHERE us.user_id = ? AND us.kind = 'offered'
                    """,
                    (m["id"],),
                ).fetchall()

                # Get next open slot
                next_slot = conn.execute(
                    """
                    SELECT id, start_time, end_time, rate_credits
                    FROM availability_slots
                    WHERE mentor_id = ? AND status = 'open' AND start_time > ?
                    ORDER BY start_time ASC
                    LIMIT 1
                    """,
                    (m["id"], now_iso),
                ).fetchone()

                eligible_skills = [s for s in skills if max_rate is None or (s["hourly_rate_credits"] or 1) <= max_rate]
                if not eligible_skills:
                    continue

                best_sim = 0.0
                matched_skill = None
                effective_rate = 1

                for sk in eligible_skills:
                    skill_rate = sk["hourly_rate_credits"] or 1
                    # Composite skill text
                    skill_corpus = f"{sk['skill_name']} {sk['category'] or ''} {sk['level']} {sk['description'] or ''} {m['bio'] or ''}"
                    skill_vec = compute_deterministic_embedding(skill_corpus)
                    sim = cosine_similarity(goal_vec, skill_vec)

                    if sim > best_sim:
                        best_sim = sim
                        matched_skill = sk["skill_name"]
                        effective_rate = skill_rate

                # Keyword match boost for eligible skills
                has_keyword = any(w.lower() in s["skill_name"].lower() for s in eligible_skills for w in goal.split())
                if has_keyword:
                    best_sim = max(best_sim, 0.75)

                if best_sim >= min_similarity:
                    if matched_skill is None:
                        matched_skill = eligible_skills[0]["skill_name"]
                        effective_rate = eligible_skills[0]["hourly_rate_credits"] or 1

                    results.append({
                        "mentor_id": m["id"],
                        "full_name": m["full_name"],
                        "avatar_url": m["avatar_url"],
                        "department": m["department"],
                        "study_year": m["study_year"],
                        "bio": m["bio"],
                        "rating": m["mentor_rating_avg"],
                        "rating_count": m["mentor_rating_count"],
                        "matched_skill": matched_skill,
                        "rate_credits": effective_rate,
                        "similarity": round(best_sim, 3),
                        "match_score": int(round(best_sim * 100)),
                        "offered_skills": [dict(s) for s in skills],
                        "next_slot": dict(next_slot) if next_slot else None,
                    })

            # Sort results by similarity DESC, then rating DESC
            results.sort(key=lambda x: (x["similarity"], x["rating"]), reverse=True)
            return results[:limit]
    finally:
        conn.close()


def get_mentor_public_profile(mentor_id: str, db_path: str = DEFAULT_DB_PATH) -> Dict:
    """
    US-07: Returns public profile for a mentor including bio, department, ratings,
    offered skills, and upcoming open availability slots.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            profile = conn.execute(
                """
                SELECT id, campus_email, full_name, avatar_url, department, study_year, bio, role,
                       mentor_rating_avg, mentor_rating_count, learner_rating_avg, learner_rating_count
                FROM profiles
                WHERE id = ? AND status = 'active'
                """,
                (mentor_id,),
            ).fetchone()
            if not profile:
                raise ValueError("Mentor profile not found.")

            skills = conn.execute(
                """
                SELECT us.id, us.level, us.description, us.hourly_rate_credits, s.name as skill_name, s.category
                FROM user_skills us
                JOIN skills s ON us.skill_id = s.id
                WHERE us.user_id = ? AND us.kind = 'offered'
                ORDER BY us.created_at ASC
                """,
                (mentor_id,),
            ).fetchall()

            now_iso = datetime.now(timezone.utc).isoformat()
            open_slots = conn.execute(
                """
                SELECT id, start_time, end_time, rate_credits, status
                FROM availability_slots
                WHERE mentor_id = ? AND status = 'open' AND start_time > ?
                ORDER BY start_time ASC
                """,
                (mentor_id, now_iso),
            ).fetchall()

            return {
                "id": profile["id"],
                "full_name": profile["full_name"],
                "avatar_url": profile["avatar_url"],
                "department": profile["department"],
                "study_year": profile["study_year"],
                "bio": profile["bio"],
                "mentor_rating_avg": profile["mentor_rating_avg"],
                "mentor_rating_count": profile["mentor_rating_count"],
                "offered_skills": [dict(s) for s in skills],
                "open_slots": [dict(s) for s in open_slots],
            }
    finally:
        conn.close()


def audit_ledger(db_path: str = DEFAULT_DB_PATH) -> Dict:
    """
    US-21 / Agreement #5: Audit zero-sum and double-entry invariants.
    1. SUM(accounts.balance) == 0
    2. SUM(debit amount) == SUM(credit amount)
    """
    conn = get_connection(db_path)
    try:
        with conn:
            sum_row = conn.execute("SELECT COALESCE(SUM(balance), 0) as total FROM accounts").fetchone()
            zero_sum_delta = sum_row["total"]

            entries_row = conn.execute(
                """
                SELECT 
                    COALESCE(SUM(CASE WHEN direction = 'debit' THEN amount ELSE 0 END), 0) as total_debits,
                    COALESCE(SUM(CASE WHEN direction = 'credit' THEN amount ELSE 0 END), 0) as total_credits
                FROM ledger_entries
                """
            ).fetchone()
            total_debits = entries_row["total_debits"]
            total_credits = entries_row["total_credits"]

            mint_row = conn.execute("SELECT balance FROM accounts WHERE kind = 'mint'").fetchone()
            total_issued = abs(mint_row["balance"]) if mint_row else 0

            passed = (zero_sum_delta == 0) and (total_debits == total_credits)

            report_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO audit_reports (id, passed, total_debits, total_credits, total_issued, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (report_id, 1 if passed else 0, total_debits, total_credits, total_issued, now),
            )

            return {
                "report_id": report_id,
                "passed": passed,
                "zero_sum_delta": zero_sum_delta,
                "total_debits": total_debits,
                "total_credits": total_credits,
                "total_issued": total_issued,
                "audited_at": now,
            }
    finally:
        conn.close()
