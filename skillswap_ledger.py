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
        """)

        # Seed system accounts: mint and escrow
        now = datetime.now(timezone.utc).isoformat()
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
                # Mint starter credits from MINT to USER account
                mint_acc = cursor.execute("SELECT id FROM accounts WHERE kind = 'mint'").fetchone()
                if not mint_acc:
                    raise LedgerError("Mint account not found.")

                # Call double-entry transfer
                post_transfer(
                    from_acc_id=mint_acc["id"],
                    to_acc_id=acc_id,
                    amount=starter_credits,
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
                    SET level = ?, description = ?, hourly_rate_credits = ?
                    WHERE id = ?
                    """,
                    (level, description, hourly_rate_credits if kind == "offered" else None, existing["id"]),
                )
            else:
                item_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO user_skills (id, user_id, skill_id, kind, level, description, hourly_rate_credits, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
