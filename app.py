import os
import sqlite3
import secrets
import psycopg

from psycopg.rows import dict_row

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from werkzeug.utils import secure_filename

from dotenv import load_dotenv


# ============================================================
# KoraCash
# User + Admin Unified Login
# Plan-Based Rewards
# Automatic Daily Activity Engine
# ============================================================

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DATABASE = os.path.join(
    BASE_DIR,
    "koracash.db",
)

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "KORACASH_SECRET_KEY",
    "koracash-development-secret-change-later",
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# ============================================================
# PAYMENT PROOF UPLOADS
# ============================================================

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

PAYMENT_PROOF_DIR = os.path.join(
    BASE_DIR,
    "static",
    "uploads",
    "payment_proofs",
)

os.makedirs(PAYMENT_PROOF_DIR, exist_ok=True)

ALLOWED_PAYMENT_PROOF_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
}


# ============================================================
# CONSTANTS
# ============================================================

REGISTRATION_BONUS = 1500
REFERRAL_BONUS = 1500

# Both plans qualify for referral reward.
REFERRAL_REQUIRED_SAVE = 3000

# ------------------------------------------------------------
# SAVE PLANS
# ------------------------------------------------------------

PLAN_3000 = 3000
PLAN_6000 = 6000

ALLOWED_SAVE_PLANS = (
    PLAN_3000,
    PLAN_6000,
)

# ------------------------------------------------------------
# REWARDS
# ------------------------------------------------------------

PLAN_3000_VIDEO_REWARD = 300
PLAN_3000_TASK_REWARD = 300

PLAN_6000_VIDEO_REWARD = 600
PLAN_6000_TASK_REWARD = 600

# Legacy fallback values.
VIDEO_REWARD = PLAN_3000_VIDEO_REWARD
TASK_REWARD = PLAN_3000_TASK_REWARD

# ------------------------------------------------------------
# WITHDRAWAL
# ------------------------------------------------------------

PLAN_3000_MIN_WITHDRAWAL = 2500
PLAN_6000_MIN_WITHDRAWAL = 5500

PLAN_3000_WITHDRAWAL_FEE_PERCENT = 3
PLAN_6000_WITHDRAWAL_FEE_PERCENT = 6

# Kept only for compatibility with old database/code.
# Withdrawals are NO LONGER locked for 3 days.
WITHDRAWAL_LOCK_DAYS = 0

PAYMENT_NUMBER = "0798386664"

MIN_VIDEO_WATCH_SECONDS = 30

TASK_ROTATION_DAYS = 4


# ============================================================
# PLAN HELPERS
# ============================================================

def normalize_plan(plan):
    """
    Convert plan values safely to integer.
    """
    try:
        plan = int(plan)
    except (TypeError, ValueError):
        return None

    if plan not in ALLOWED_SAVE_PLANS:
        return None

    return plan


def get_plan_name(plan):
    plan = normalize_plan(plan)

    if plan == PLAN_3000:
        return "Plan 3,000"

    if plan == PLAN_6000:
        return "Plan 6,000"

    return "No Plan"


def get_video_reward_for_plan(plan):
    plan = normalize_plan(plan)

    if plan == PLAN_6000:
        return PLAN_6000_VIDEO_REWARD

    if plan == PLAN_3000:
        return PLAN_3000_VIDEO_REWARD

    return 0


def get_task_reward_for_plan(plan):
    plan = normalize_plan(plan)

    if plan == PLAN_6000:
        return PLAN_6000_TASK_REWARD

    if plan == PLAN_3000:
        return PLAN_3000_TASK_REWARD

    return 0


def get_min_withdrawal_for_plan(plan):
    plan = normalize_plan(plan)

    if plan == PLAN_6000:
        return PLAN_6000_MIN_WITHDRAWAL

    if plan == PLAN_3000:
        return PLAN_3000_MIN_WITHDRAWAL

    return 0


def get_withdrawal_fee_percent(plan):
    plan = normalize_plan(plan)

    if plan == PLAN_6000:
        return PLAN_6000_WITHDRAWAL_FEE_PERCENT

    if plan == PLAN_3000:
        return PLAN_3000_WITHDRAWAL_FEE_PERCENT

    return 0


def calculate_withdrawal_fee(
    amount,
    plan,
):
    """
    Fee is calculated from requested/gross withdrawal amount.
    """
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return 0

    fee_percent = get_withdrawal_fee_percent(plan)

    if fee_percent <= 0:
        return 0

    return (
        amount * fee_percent
    ) // 100


def calculate_withdrawal_net(
    amount,
    plan,
):
    fee = calculate_withdrawal_fee(
        amount,
        plan,
    )

    return max(
        0,
        int(amount) - fee,
    )


def plan_is_valid_for_user(user):
    return bool(
        user
        and normalize_plan(
            user["save_plan"]
        )
    )


# ============================================================
# DATABASE ROW HELPERS
# ============================================================

class HybridRow(dict):

    def __getitem__(self, key):

        if isinstance(key, int):
            return list(
                self.values()
            )[key]

        return super().__getitem__(key)


class DatabaseCursor:

    def __init__(self, cursor):
        self.cursor = cursor

    @property
    def rowcount(self):
        return self.cursor.rowcount

    @property
    def lastrowid(self):
        raise AttributeError(
            "PostgreSQL does not provide lastrowid. "
            "Use RETURNING id."
        )

    def _convert_row(self, row):

        if row is None:
            return None

        if isinstance(row, dict):
            return HybridRow(row)

        try:

            return HybridRow(
                zip(
                    [
                        column[0]
                        for column in self.cursor.description
                    ],
                    row,
                )
            )

        except Exception:

            return row

    def fetchone(self):

        row = self.cursor.fetchone()

        return self._convert_row(row)

    def fetchall(self):

        rows = self.cursor.fetchall()

        return [
            self._convert_row(row)
            for row in rows
        ]

    def __getattr__(self, name):
        return getattr(
            self.cursor,
            name,
        )


class DatabaseConnection:

    def __init__(self, connection):
        self.connection = connection

    def _convert_sql(self, sql):

        if not DATABASE_URL:
            return sql

        sql = sql.replace(
            "BEGIN IMMEDIATE",
            "BEGIN",
        )

        return sql.replace(
            "?",
            "%s",
        )

    def execute(
        self,
        sql,
        params=None,
    ):

        sql = self._convert_sql(sql)

        if params is None:

            cursor = self.connection.execute(
                sql
            )

        else:

            cursor = self.connection.execute(
                sql,
                params,
            )

        return DatabaseCursor(cursor)

    def executemany(
        self,
        sql,
        params,
    ):

        sql = self._convert_sql(sql)

        cursor = self.connection.executemany(
            sql,
            params,
        )

        return DatabaseCursor(cursor)

    def executescript(self, script):

        if DATABASE_URL:

            raise RuntimeError(
                "SQLite executescript() cannot be used with Neon."
            )

        return self.connection.executescript(
            script
        )

    def commit(self):
        return self.connection.commit()

    def rollback(self):
        return self.connection.rollback()

    def close(self):
        return self.connection.close()


def get_db():

    if DATABASE_URL:

        conn = psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
        )

        return DatabaseConnection(conn)

    conn = sqlite3.connect(
        DATABASE,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return DatabaseConnection(conn)


# ============================================================
# DATABASE MIGRATION HELPERS
# ============================================================

def ensure_column(
    conn,
    table_name,
    column_name,
    definition,
):

    if DATABASE_URL:

        columns = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = ?
            """,
            (
                table_name,
            ),
        ).fetchall()

        existing_columns = {
            column["column_name"]
            for column in columns
        }

    else:

        columns = conn.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()

        existing_columns = {
            column["name"]
            for column in columns
        }

    if column_name not in existing_columns:

        conn.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {definition}
            """
        )


def migrate_database(conn):

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    ensure_column(
        conn,
        "users",
        "save_plan",
        "INTEGER",
    )
    ensure_column(
        conn,
        "cash_ins",
        "payment_proof",
        "TEXT",
    )

    ensure_column(
        conn,
        "cash_ins",
        "ocr_text",
        "TEXT",
    )

    ensure_column(
        conn,
        "cash_ins",
        "verification_status",
        "TEXT DEFAULT 'Pending'",
    )

    ensure_column(
        conn,
        "cash_ins",
        "verified_amount",
        "INTEGER",
    )

    ensure_column(
        conn,
        "cash_ins",
        "verified_recipient",
        "TEXT",
    )

    ensure_column(
        conn,
        "cash_ins",
        "verified_phone",
        "TEXT",
    )

    ensure_column(
        conn,
        "cash_ins",
        "transaction_reference",
        "TEXT",
    )
    ensure_column(
        conn,
        "users",
        "withdrawal_locked_until",
        "TEXT",
    )

    # --------------------------------------------------------
    # CASH INS
    # --------------------------------------------------------

    ensure_column(
        conn,
        "cash_ins",
        "save_plan",
        "INTEGER",
    )

    # --------------------------------------------------------
    # WITHDRAWALS
    # --------------------------------------------------------

    ensure_column(
        conn,
        "withdrawals",
        "fee",
        "INTEGER NOT NULL DEFAULT 0",
    )

    ensure_column(
        conn,
        "withdrawals",
        "net_amount",
        "INTEGER NOT NULL DEFAULT 0",
    )

    # --------------------------------------------------------
    # VIDEOS
    # --------------------------------------------------------

    ensure_column(
        conn,
        "videos",
        "duration_seconds",
        "INTEGER DEFAULT 0",
    )

    ensure_column(
        conn,
        "videos",
        "category",
        "TEXT DEFAULT 'General'",
    )

    ensure_column(
        conn,
        "videos",
        "source",
        "TEXT DEFAULT 'Unknown'",
    )

    ensure_column(
        conn,
        "videos",
        "license",
        "TEXT DEFAULT 'Unknown'",
    )

    # --------------------------------------------------------
    # TASKS
    # --------------------------------------------------------

    ensure_column(
        conn,
        "tasks",
        "category",
        "TEXT DEFAULT 'General'",
    )

    ensure_column(
        conn,
        "tasks",
        "option_a",
        "TEXT",
    )

    ensure_column(
        conn,
        "tasks",
        "option_b",
        "TEXT",
    )

    ensure_column(
        conn,
        "tasks",
        "option_c",
        "TEXT",
    )

    ensure_column(
        conn,
        "tasks",
        "option_d",
        "TEXT",
    )

    ensure_column(
        conn,
        "tasks",
        "correct_answer",
        "TEXT",
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    conn = get_db()

    try:

        if not DATABASE_URL:

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    phone TEXT UNIQUE NOT NULL,

                    password_hash TEXT NOT NULL,

                    referral_code TEXT UNIQUE NOT NULL,

                    referred_by INTEGER,

                    save_plan INTEGER,

                    saved_balance INTEGER NOT NULL DEFAULT 0,

                    withdrawable_balance INTEGER NOT NULL DEFAULT 0,

                    total_earned INTEGER NOT NULL DEFAULT 0,

                    total_withdrawn INTEGER NOT NULL DEFAULT 0,

                    registration_bonus INTEGER NOT NULL DEFAULT 1500,

                    created_at TEXT NOT NULL,

                    last_login TEXT,

                    withdrawal_locked_until TEXT,

                    is_active INTEGER NOT NULL DEFAULT 1,

                    FOREIGN KEY (referred_by)
                        REFERENCES users(id)
                        ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL,

                    transaction_type TEXT NOT NULL,

                    amount INTEGER NOT NULL,

                    status TEXT NOT NULL DEFAULT 'Completed',

                    description TEXT,

                    created_at TEXT NOT NULL,

                    FOREIGN KEY (user_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS cash_ins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL,

                    amount INTEGER NOT NULL,

                    save_plan INTEGER,

                    payment_number TEXT NOT NULL,

                    status TEXT NOT NULL DEFAULT 'Pending',

                    created_at TEXT NOT NULL,

                    confirmed_at TEXT,

                    FOREIGN KEY (user_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL,

                    amount INTEGER NOT NULL,

                    fee INTEGER NOT NULL DEFAULT 0,

                    net_amount INTEGER NOT NULL DEFAULT 0,

                    network TEXT NOT NULL,

                    phone TEXT NOT NULL,

                    status TEXT NOT NULL DEFAULT 'Pending',

                    created_at TEXT NOT NULL,

                    completed_at TEXT,

                    FOREIGN KEY (user_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    title TEXT NOT NULL,

                    description TEXT,

                    video_url TEXT,

                    reward INTEGER NOT NULL DEFAULT 300,

                    is_active INTEGER NOT NULL DEFAULT 1,

                    created_at TEXT NOT NULL,

                    duration_seconds INTEGER DEFAULT 0,

                    category TEXT DEFAULT 'General',

                    source TEXT DEFAULT 'Unknown',

                    license TEXT DEFAULT 'Unknown'
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    title TEXT NOT NULL,

                    description TEXT,

                    reward INTEGER NOT NULL DEFAULT 300,

                    is_active INTEGER NOT NULL DEFAULT 1,

                    created_at TEXT NOT NULL,

                    category TEXT DEFAULT 'General',

                    option_a TEXT,

                    option_b TEXT,

                    option_c TEXT,

                    option_d TEXT,

                    correct_answer TEXT
                );

                CREATE TABLE IF NOT EXISTS daily_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL,

                    activity_date TEXT NOT NULL,

                    video_id INTEGER,

                    task_id INTEGER,

                    video_completed INTEGER NOT NULL DEFAULT 0,

                    task_completed INTEGER NOT NULL DEFAULT 0,

                    video_rewarded INTEGER NOT NULL DEFAULT 0,

                    task_rewarded INTEGER NOT NULL DEFAULT 0,

                    created_at TEXT NOT NULL,

                    UNIQUE(user_id, activity_date),

                    FOREIGN KEY (user_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    FOREIGN KEY (video_id)
                        REFERENCES videos(id)
                        ON DELETE SET NULL,

                    FOREIGN KEY (task_id)
                        REFERENCES tasks(id)
                        ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS task_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL,

                    task_id INTEGER NOT NULL,

                    activity_date TEXT NOT NULL,

                    answer TEXT NOT NULL,

                    status TEXT NOT NULL DEFAULT 'Pending',

                    submitted_at TEXT NOT NULL,

                    reviewed_at TEXT,

                    reviewer_note TEXT,

                    UNIQUE(
                        user_id,
                        task_id,
                        activity_date
                    ),

                    FOREIGN KEY (user_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    FOREIGN KEY (task_id)
                        REFERENCES tasks(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    referrer_id INTEGER NOT NULL,

                    referred_user_id INTEGER NOT NULL,

                    bonus_amount INTEGER NOT NULL DEFAULT 1500,

                    status TEXT NOT NULL DEFAULT 'Pending',

                    created_at TEXT NOT NULL,

                    rewarded_at TEXT,

                    UNIQUE(referred_user_id),

                    FOREIGN KEY (referrer_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    FOREIGN KEY (referred_user_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    user_id INTEGER NOT NULL,

                    title TEXT NOT NULL,

                    message TEXT NOT NULL,

                    is_read INTEGER NOT NULL DEFAULT 0,

                    created_at TEXT NOT NULL,

                    FOREIGN KEY (user_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_daily_user_date
                ON daily_activities(user_id, activity_date);

                CREATE INDEX IF NOT EXISTS idx_task_submissions_user_date
                ON task_submissions(user_id, activity_date);

                CREATE INDEX IF NOT EXISTS idx_task_submissions_status
                ON task_submissions(status);

                CREATE INDEX IF NOT EXISTS idx_videos_active
                ON videos(is_active);

                CREATE INDEX IF NOT EXISTS idx_tasks_active
                ON tasks(is_active);

                CREATE INDEX IF NOT EXISTS idx_cash_ins_status
                ON cash_ins(status);

                CREATE INDEX IF NOT EXISTS idx_withdrawals_status
                ON withdrawals(status);
                """
            )

        else:

            # Neon tables already exist.
            # Only migrations are performed here.

            migrate_database(
                conn
            )

        # SQLite migrations also run here.
        migrate_database(
            conn
        )

        seed_content(
            conn
        )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# TIME HELPERS
# ============================================================

def now_utc():
    return datetime.now(
        timezone.utc
    )


def now_iso():
    return now_utc().isoformat()


def today_string():

    rwanda_time = datetime.now(
        ZoneInfo("Africa/Kigali")
    )

    return rwanda_time.strftime(
        "%Y-%m-%d"
    )


# ============================================================
# SEED CONTENT
# ============================================================

def seed_content(conn):

    video_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM videos
        """
    ).fetchone()["count"]

    task_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM tasks
        """
    ).fetchone()["count"]

    now = now_iso()

    if video_count == 0:

        videos = [
            (
                "Daily Video 1",
                "Watch today's KoraCash learning video.",
                "https://example.com/video1",
                PLAN_3000_VIDEO_REWARD,
                now,
            ),
            (
                "Daily Video 2",
                "Watch today's KoraCash learning video.",
                "https://example.com/video2",
                PLAN_3000_VIDEO_REWARD,
                now,
            ),
            (
                "Daily Video 3",
                "Watch today's KoraCash learning video.",
                "https://example.com/video3",
                PLAN_3000_VIDEO_REWARD,
                now,
            ),
            (
                "Daily Video 4",
                "Watch today's KoraCash learning video.",
                "https://example.com/video4",
                PLAN_3000_VIDEO_REWARD,
                now,
            ),
            (
                "Daily Video 5",
                "Watch today's KoraCash learning video.",
                "https://example.com/video5",
                PLAN_3000_VIDEO_REWARD,
                now,
            ),
        ]

        conn.executemany(
            """
            INSERT INTO videos
            (
                title,
                description,
                video_url,
                reward,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            videos,
        )

    if task_count == 0:

        tasks = [
            (
                "Daily Task 1",
                "Complete today's task.",
                PLAN_3000_TASK_REWARD,
                now,
            ),
            (
                "Daily Task 2",
                "Complete today's task.",
                PLAN_3000_TASK_REWARD,
                now,
            ),
            (
                "Daily Task 3",
                "Complete today's task.",
                PLAN_3000_TASK_REWARD,
                now,
            ),
            (
                "Daily Task 4",
                "Complete today's task.",
                PLAN_3000_TASK_REWARD,
                now,
            ),
            (
                "Daily Task 5",
                "Complete today's task.",
                PLAN_3000_TASK_REWARD,
                now,
            ),
        ]

        conn.executemany(
            """
            INSERT INTO tasks
            (
                title,
                description,
                reward,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            tasks,
        )


# ============================================================
# USER HELPERS
# ============================================================

def current_user():

    user_id = session.get(
        "user_id"
    )

    if not user_id:
        return None

    conn = get_db()

    try:

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        return user

    finally:

        conn.close()


def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get(
            "user_id"
        ):

            flash(
                "Please login first.",
                "warning",
            )

            return redirect(
                url_for("login")
            )

        user = current_user()

        if not user:

            session.clear()

            flash(
                "Your account could not be found.",
                "danger",
            )

            return redirect(
                url_for("login")
            )

        if not user["is_active"]:

            session.clear()

            flash(
                "Your account is inactive.",
                "danger",
            )

            return redirect(
                url_for("login")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


# ============================================================
# NOTIFICATIONS
# ============================================================

def create_notification(
    user_id,
    title,
    message,
):

    conn = get_db()

    try:

        conn.execute(
            """
            INSERT INTO notifications
            (
                user_id,
                title,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                title,
                message,
                now_iso(),
            ),
        )

        conn.commit()

    finally:

        conn.close()


# ============================================================
# TRANSACTIONS / LEDGER
# ============================================================

def create_transaction(
    conn,
    user_id,
    transaction_type,
    amount,
    description,
    status="Completed",
):

    conn.execute(
        """
        INSERT INTO transactions
        (
            user_id,
            transaction_type,
            amount,
            status,
            description,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            transaction_type,
            int(amount),
            status,
            description,
            now_iso(),
        ),
    )


# ============================================================
# REFERRAL CODE
# ============================================================

def generate_referral_code():

    while True:

        code = (
            "KC-"
            + secrets.token_hex(4).upper()
        )

        conn = get_db()

        try:

            exists = conn.execute(
                """
                SELECT id
                FROM users
                WHERE referral_code = ?
                """,
                (
                    code,
                ),
            ).fetchone()

        finally:

            conn.close()

        if not exists:
            return code


# ============================================================
# DAILY ACTIVITY HELPERS
# ============================================================

def get_valid_video(
    conn,
    video_id,
):

    if not video_id:
        return None

    return conn.execute(
        """
        SELECT *
        FROM videos
        WHERE id = ?
        AND is_active = 1
        AND video_url IS NOT NULL
        AND TRIM(video_url) != ''
        """,
        (
            video_id,
        ),
    ).fetchone()


def get_valid_task(
    conn,
    task_id,
):

    if not task_id:
        return None

    return conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        AND is_active = 1
        AND option_a IS NOT NULL
        AND option_b IS NOT NULL
        AND option_c IS NOT NULL
        AND option_d IS NOT NULL
        AND correct_answer IS NOT NULL
        AND UPPER(TRIM(correct_answer))
            IN ('A', 'B', 'C', 'D')
        """,
        (
            task_id,
        ),
    ).fetchone()


def choose_daily_video(
    conn,
    user_id,
    date_value,
):

    # --------------------------------------------------------
    # Cross-database implementation.
    # Avoids SQLite/PostgreSQL date syntax differences.
    # --------------------------------------------------------

    try:

        current_date = datetime.strptime(
            date_value,
            "%Y-%m-%d",
        ).date()

    except ValueError:

        current_date = datetime.now().date()

    cutoff_date = (
        current_date
        - timedelta(
            days=TASK_ROTATION_DAYS
        )
    ).isoformat()

    recent = conn.execute(
        """
        SELECT video_id
        FROM daily_activities
        WHERE user_id = ?
        AND video_id IS NOT NULL
        AND activity_date >= ?
        """,
        (
            user_id,
            cutoff_date,
        ),
    ).fetchall()

    excluded_ids = {
        row["video_id"]
        for row in recent
        if row["video_id"] is not None
    }

    videos = conn.execute(
        """
        SELECT *
        FROM videos
        WHERE is_active = 1
        AND video_url IS NOT NULL
        AND TRIM(video_url) != ''
        ORDER BY RANDOM()
        """
    ).fetchall()

    for video in videos:

        if video["id"] not in excluded_ids:
            return video

    if videos:
        return videos[0]

    return None


def choose_daily_task(
    conn,
    user_id,
    date_value,
):

    try:

        current_date = datetime.strptime(
            date_value,
            "%Y-%m-%d",
        ).date()

    except ValueError:

        current_date = datetime.now().date()

    cutoff_date = (
        current_date
        - timedelta(
            days=TASK_ROTATION_DAYS
        )
    ).isoformat()

    recent = conn.execute(
        """
        SELECT task_id
        FROM daily_activities
        WHERE user_id = ?
        AND task_id IS NOT NULL
        AND activity_date >= ?
        """,
        (
            user_id,
            cutoff_date,
        ),
    ).fetchall()

    excluded_ids = {
        row["task_id"]
        for row in recent
        if row["task_id"] is not None
    }

    tasks = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE is_active = 1

        AND option_a IS NOT NULL
        AND option_b IS NOT NULL
        AND option_c IS NOT NULL
        AND option_d IS NOT NULL

        AND correct_answer IS NOT NULL

        AND UPPER(TRIM(correct_answer))
            IN ('A', 'B', 'C', 'D')

        ORDER BY RANDOM()
        """
    ).fetchall()

    for task in tasks:

        if task["id"] not in excluded_ids:
            return task

    if tasks:
        return tasks[0]

    return None


# ============================================================
# DAILY ACTIVITY ENGINE
# ============================================================

def get_or_create_daily_activity(
    user_id
):

    date_value = today_string()

    conn = get_db()

    try:

        activity = conn.execute(
            """
            SELECT *
            FROM daily_activities
            WHERE user_id = ?
            AND activity_date = ?
            """,
            (
                user_id,
                date_value,
            ),
        ).fetchone()

        if activity:

            current_video = get_valid_video(
                conn,
                activity["video_id"],
            )

            current_task = get_valid_task(
                conn,
                activity["task_id"],
            )

            new_video_id = activity[
                "video_id"
            ]

            new_task_id = activity[
                "task_id"
            ]

            changed = False

            if not current_video:

                video = choose_daily_video(
                    conn,
                    user_id,
                    date_value,
                )

                new_video_id = (
                    video["id"]
                    if video
                    else None
                )

                if new_video_id != activity[
                    "video_id"
                ]:

                    changed = True

            if not current_task:

                task = choose_daily_task(
                    conn,
                    user_id,
                    date_value,
                )

                new_task_id = (
                    task["id"]
                    if task
                    else None
                )

                if new_task_id != activity[
                    "task_id"
                ]:

                    changed = True

            if changed:

                conn.execute(
                    """
                    UPDATE daily_activities
                    SET
                        video_id = ?,
                        task_id = ?
                    WHERE id = ?
                    """,
                    (
                        new_video_id,
                        new_task_id,
                        activity["id"],
                    ),
                )

                conn.commit()

                activity = conn.execute(
                    """
                    SELECT *
                    FROM daily_activities
                    WHERE id = ?
                    """,
                    (
                        activity["id"],
                    ),
                ).fetchone()

            return activity

        video = choose_daily_video(
            conn,
            user_id,
            date_value,
        )

        task = choose_daily_task(
            conn,
            user_id,
            date_value,
        )

        video_id = (
            video["id"]
            if video
            else None
        )

        task_id = (
            task["id"]
            if task
            else None
        )

        try:

            conn.execute(
                """
                INSERT INTO daily_activities
                (
                    user_id,
                    activity_date,
                    video_id,
                    task_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    date_value,
                    video_id,
                    task_id,
                    now_iso(),
                ),
            )

            conn.commit()

        except Exception:

            conn.rollback()

        return conn.execute(
            """
            SELECT *
            FROM daily_activities
            WHERE user_id = ?
            AND activity_date = ?
            """,
            (
                user_id,
                date_value,
            ),
        ).fetchone()

    finally:

        conn.close()


# ============================================================
# SAVED MONEY / PLAN
# ============================================================

def has_saved_money(
    user_id
):

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT
                saved_balance,
                save_plan
            FROM users
            WHERE id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        return bool(
            row
            and row["saved_balance"] > 0
            and normalize_plan(
                row["save_plan"]
            )
        )

    finally:

        conn.close()


def get_user_plan(
    user_id
):

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT save_plan
            FROM users
            WHERE id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        if not row:
            return None

        return normalize_plan(
            row["save_plan"]
        )

    finally:

        conn.close()


# ============================================================
# WITHDRAWAL LOCK
# ============================================================

def get_withdrawal_lock(
    user
):

    # New business logic:
    # There is NO 3-day withdrawal lock.

    return None


# ============================================================
# REFERRAL REWARD
# ============================================================

def reward_referral_after_save(
    conn,
    referred_user_id,
    save_amount,
):

    if save_amount < REFERRAL_REQUIRED_SAVE:
        return False

    referral = conn.execute(
        """
        SELECT *
        FROM referrals
        WHERE referred_user_id = ?
        AND status = 'Pending'
        LIMIT 1
        """,
        (
            referred_user_id,
        ),
    ).fetchone()

    if not referral:
        return False

    referrer = conn.execute(
        """
        SELECT id, phone, is_active
        FROM users
        WHERE id = ?
        """,
        (
            referral["referrer_id"],
        ),
    ).fetchone()

    if not referrer:
        return False

    # --------------------------------------------------------
    # Prevent reward to inactive/deleted account.
    # --------------------------------------------------------

    if not referrer["is_active"]:
        return False

    updated = conn.execute(
        """
        UPDATE users
        SET
            withdrawable_balance =
                withdrawable_balance + ?,

            total_earned =
                total_earned + ?

        WHERE id = ?
        """,
        (
            REFERRAL_BONUS,
            REFERRAL_BONUS,
            referral["referrer_id"],
        ),
    )

    if updated.rowcount != 1:
        return False

    create_transaction(
        conn,
        referral["referrer_id"],
        "REFERRAL_BONUS",
        REFERRAL_BONUS,
        (
            "Referral bonus after referred user "
            "completed an approved Save."
        ),
        status="Completed",
    )

    conn.execute(
        """
        INSERT INTO notifications
        (
            user_id,
            title,
            message,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            referral["referrer_id"],
            "Referral Bonus",
            (
                f"You received {REFERRAL_BONUS:,} Frw "
                "referral bonus because your referred "
                "user completed a confirmed Save."
            ),
            now_iso(),
        ),
    )

    conn.execute(
        """
        UPDATE referrals
        SET
            status = 'Completed',
            rewarded_at = ?

        WHERE id = ?
        AND status = 'Pending'
        """,
        (
            now_iso(),
            referral["id"],
        ),
    )

    return True


# ============================================================
# CASH IN CONFIRMATION
# ============================================================

def confirm_cash_in(
    cash_in_id,
    confirmed_amount=None,
):

    conn = get_db()

    try:

        cash_in = conn.execute(
            """
            SELECT *
            FROM cash_ins
            WHERE id = ?
            """,
            (
                cash_in_id,
            ),
        ).fetchone()

        if not cash_in:

            return {
                "success": False,
                "message": "Save request not found.",
            }

        if cash_in["status"] == "Completed":

            return {
                "success": False,
                "message": "Save has already been confirmed.",
            }

        if cash_in["status"] != "Pending":

            return {
                "success": False,
                "message": "Save cannot be confirmed.",
            }

        amount = (
            confirmed_amount
            if confirmed_amount is not None
            else cash_in["amount"]
        )

        try:
            amount = int(amount)
        except (TypeError, ValueError):

            return {
                "success": False,
                "message": "Invalid confirmation amount.",
            }

        if amount not in ALLOWED_SAVE_PLANS:

            return {
                "success": False,
                "message": (
                    "Save amount must be either "
                    "3,000 Frw or 6,000 Frw."
                ),
            }

        user_id = cash_in[
            "user_id"
        ]

        selected_plan = normalize_plan(
            cash_in["save_plan"]
        )

        if not selected_plan:
            selected_plan = amount

        if selected_plan != amount:

            return {
                "success": False,
                "message": (
                    "The confirmed amount does not "
                    "match the selected Save plan."
                ),
            }

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        if not user:

            return {
                "success": False,
                "message": "User account not found.",
            }

        existing_plan = normalize_plan(
            user["save_plan"]
        )

        if existing_plan and existing_plan != selected_plan:

            return {
                "success": False,
                "message": (
                    "This user already has a different "
                    "active Save plan."
                ),
            }

        updated = conn.execute(
            """
            UPDATE cash_ins
            SET
                amount = ?,
                save_plan = ?,
                status = 'Completed',
                confirmed_at = ?

            WHERE id = ?
            AND status = 'Pending'
            """,
            (
                amount,
                selected_plan,
                now_iso(),
                cash_in_id,
            ),
        )

        if updated.rowcount != 1:

            conn.rollback()

            return {
                "success": False,
                "message": (
                    "Save has already been processed."
                ),
            }

                # ----------------------------------------------------
        # APPROVED SAVE
        #
        # Save is added ONLY to:
        # 1. saved_balance
        #
        # Save money is NOT withdrawable.
        # Registration bonus and activity rewards
        # remain in withdrawable_balance.
        # ----------------------------------------------------

        conn.execute(
            """
            UPDATE users
            SET
                save_plan = ?,
                saved_balance =
                    saved_balance + ?
            WHERE id = ?
            """,
            (
                selected_plan,
                amount,
                user_id,
            ),
        )
        create_transaction(
            conn,
            user_id,
            "SAVE",
            amount,
            (
                f"Approved Save - "
                f"{get_plan_name(selected_plan)}"
            ),
            status="Completed",
        )

        conn.execute(
            """
            INSERT INTO notifications
            (
                user_id,
                title,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                "Save Approved",
                (
                    f"Your {amount:,} Frw Save has been "
                    "approved. The amount has been added "
                    "to your account balance."
                ),
                now_iso(),
            ),
        )

        referral_rewarded = reward_referral_after_save(
            conn,
            user_id,
            amount,
        )

        conn.commit()

        return {
            "success": True,
            "cash_in_id": cash_in_id,
            "amount": amount,
            "plan": selected_plan,
            "referral_rewarded": referral_rewarded,
            "message": (
                "Save confirmed successfully."
            ),
        }

    except Exception as error:

        conn.rollback()

        print(
            "SAVE CONFIRMATION ERROR:",
            error,
        )

        return {
            "success": False,
            "message": (
                "Save confirmation failed."
            ),
            "error": str(error),
        }

    finally:

        conn.close()


# ============================================================
# INDEX
# ============================================================

@app.route("/")
def index():

    if session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

    if session.get(
        "user_id"
    ):

        return redirect(
            url_for("home")
        )

    return redirect(
        url_for("login")
    )


# ============================================================
# HOME
# ============================================================

@app.route("/home")
@login_required
def home():

    user = current_user()

    activity = None
    video = None
    task = None
    task_submission = None

    unlocked = has_saved_money(
        user["id"]
    )

    if unlocked:

        activity = get_or_create_daily_activity(
            user["id"]
        )

        conn = get_db()

        try:

            if activity and activity[
                "video_id"
            ]:

                video = conn.execute(
                    """
                    SELECT *
                    FROM videos
                    WHERE id = ?
                    """,
                    (
                        activity[
                            "video_id"
                        ],
                    ),
                ).fetchone()

            if activity and activity[
                "task_id"
            ]:

                task = conn.execute(
                    """
                    SELECT *
                    FROM tasks
                    WHERE id = ?
                    """,
                    (
                        activity[
                            "task_id"
                        ],
                    ),
                ).fetchone()

                task_submission = conn.execute(
                    """
                    SELECT *
                    FROM task_submissions
                    WHERE user_id = ?
                    AND task_id = ?
                    AND activity_date = ?
                    """,
                    (
                        user["id"],
                        activity[
                            "task_id"
                        ],
                        today_string(),
                    ),
                ).fetchone()

        finally:

            conn.close()

    conn = get_db()

    try:

        activity_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE user_id = ?
            AND transaction_type IN
            (
                'VIDEO_REWARD',
                'TASK_REWARD'
            )
            AND status = 'Completed'
            """,
            (
                user["id"],
            ),
        ).fetchone()[0]

        unread_notifications = conn.execute(
            """
            SELECT COUNT(*)
            FROM notifications
            WHERE user_id = ?
            AND is_read = 0
            """,
            (
                user["id"],
            ),
        ).fetchone()[0]

    finally:

        conn.close()

    return render_template(
        "home.html",
        user=user,
        activity=activity,
        video=video,
        task=task,
        task_submission=task_submission,
        unlocked=unlocked,
        activity_count=activity_count,
        unread_notifications=unread_notifications,
        min_video_watch_seconds=MIN_VIDEO_WATCH_SECONDS,

        # New plan information for templates.
        plan_name=get_plan_name(
            user["save_plan"]
        ),
        video_reward=get_video_reward_for_plan(
            user["save_plan"]
        ),
        task_reward=get_task_reward_for_plan(
            user["save_plan"]
        ),
        minimum_withdrawal=get_min_withdrawal_for_plan(
            user["save_plan"]
        ),
        withdrawal_fee_percent=get_withdrawal_fee_percent(
            user["save_plan"]
        ),
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"],
)
def register():

    if session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

    if session.get(
        "user_id"
    ):

        return redirect(
            url_for("home")
        )

    referral_from_url = request.args.get(
        "ref",
        "",
    ).strip().upper()

    if request.method == "POST":

        phone = request.form.get(
            "phone",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        referral_code = request.form.get(
            "referral_code",
            referral_from_url,
        ).strip().upper()

        if not phone:

            flash(
                "Phone number is required.",
                "danger",
            )

            return render_template(
                "register.html",
                referral_code=referral_code,
            )

        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "danger",
            )

            return render_template(
                "register.html",
                referral_code=referral_code,
            )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger",
            )

            return render_template(
                "register.html",
                referral_code=referral_code,
            )

        conn = get_db()

        try:

            existing = conn.execute(
                """
                SELECT id
                FROM users
                WHERE phone = ?
                """,
                (
                    phone,
                ),
            ).fetchone()

            if existing:

                flash(
                    "An account with this phone already exists.",
                    "danger",
                )

                return render_template(
                    "register.html",
                    referral_code=referral_code,
                )

            referrer = None

            if referral_code:

                referrer = conn.execute(
                    """
                    SELECT
                        id,
                        phone,
                        referral_code
                    FROM users
                    WHERE referral_code = ?
                    AND is_active = 1
                    """,
                    (
                        referral_code,
                    ),
                ).fetchone()

                if not referrer:

                    flash(
                        "Referral code is invalid.",
                        "danger",
                    )

                    return render_template(
                        "register.html",
                        referral_code=referral_code,
                    )

                if referrer["phone"] == phone:

                    flash(
                        "You cannot use your own referral code.",
                        "danger",
                    )

                    return render_template(
                        "register.html",
                        referral_code=referral_code,
                    )

            user_referral_code = (
                generate_referral_code()
            )

            password_hash = (
                generate_password_hash(
                    password
                )
            )

            created_at = now_iso()

            if DATABASE_URL:

                cursor = conn.execute(
                    """
                    INSERT INTO users
                    (
                        phone,
                        password_hash,
                        referral_code,
                        referred_by,
                        save_plan,
                        withdrawable_balance,
                        total_earned,
                        registration_bonus,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id
                    """,
                    (
                        phone,
                        password_hash,
                        user_referral_code,
                        (
                            referrer["id"]
                            if referrer
                            else None
                        ),
                        None,
                        REGISTRATION_BONUS,
                        REGISTRATION_BONUS,
                        REGISTRATION_BONUS,
                        created_at,
                    ),
                )

                user_id = cursor.fetchone()[
                    "id"
                ]

            else:

                cursor = conn.execute(
                    """
                    INSERT INTO users
                    (
                        phone,
                        password_hash,
                        referral_code,
                        referred_by,
                        save_plan,
                        withdrawable_balance,
                        total_earned,
                        registration_bonus,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        phone,
                        password_hash,
                        user_referral_code,
                        (
                            referrer["id"]
                            if referrer
                            else None
                        ),
                        None,
                        REGISTRATION_BONUS,
                        REGISTRATION_BONUS,
                        REGISTRATION_BONUS,
                        created_at,
                    ),
                )

                user_id = cursor.lastrowid

            create_transaction(
                conn,
                user_id,
                "REGISTRATION_BONUS",
                REGISTRATION_BONUS,
                "Welcome registration bonus",
                status="Completed",
            )

            conn.execute(
                """
                INSERT INTO notifications
                (
                    user_id,
                    title,
                    message,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    "Welcome to KoraCash",
                    (
                        "You received a 1,500 Frw "
                        "Welcome Bonus. It is available "
                        "for withdrawal according to "
                        "the withdrawal rules."
                    ),
                    now_iso(),
                ),
            )

            if referrer:

                conn.execute(
                    """
                    INSERT INTO referrals
                    (
                        referrer_id,
                        referred_user_id,
                        bonus_amount,
                        status,
                        created_at,
                        rewarded_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        referrer["id"],
                        user_id,
                        REFERRAL_BONUS,
                        "Pending",
                        now_iso(),
                        None,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO notifications
                    (
                        user_id,
                        title,
                        message,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        referrer["id"],
                        "New Referral",
                        (
                            "A new user joined using your "
                            "referral link. You will receive "
                            f"{REFERRAL_BONUS:,} Frw after "
                            "their confirmed Save."
                        ),
                        now_iso(),
                    ),
                )

            conn.commit()

        except Exception as error:

            conn.rollback()

            print(
                "REGISTRATION ERROR:",
                error,
            )

            flash(
                (
                    "Registration could not be completed. "
                    "Please try again."
                ),
                "danger",
            )

            return render_template(
                "register.html",
                referral_code=referral_code,
            )

        finally:

            conn.close()

        flash(
            (
                "Registration successful. "
                "You received 1,500 Frw Welcome Bonus."
            ),
            "success",
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html",
        referral_code=referral_from_url,
    )


# ============================================================
# UNIFIED LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"],
)
def login():

    if session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

    if session.get(
        "user_id"
    ):

        return redirect(
            url_for("home")
        )

    if request.method == "POST":

        phone = request.form.get(
            "phone",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        if not phone or not password:

            flash(
                "Phone number and password are required.",
                "danger",
            )

            return render_template(
                "login.html"
            )

        try:

            from admin import (
                ADMIN_PHONE,
                ADMIN_PASSWORD,
            )

        except ImportError:

            ADMIN_PHONE = os.getenv(
                "ADMIN_PHONE",
                "",
            )

            ADMIN_PASSWORD = os.getenv(
                "ADMIN_PASSWORD",
                "",
            )

        # ----------------------------------------------------
        # ADMIN LOGIN
        # ----------------------------------------------------

        if (
            phone == ADMIN_PHONE
            and password == ADMIN_PASSWORD
        ):

            session.clear()

            session[
                "admin_logged_in"
            ] = True

            session[
                "admin_phone"
            ] = phone

            return redirect(
                url_for(
                    "admin.admin_dashboard"
                )
            )

        # ----------------------------------------------------
        # NORMAL USER LOGIN
        # ----------------------------------------------------

        conn = get_db()

        try:

            user = conn.execute(
                """
                SELECT *
                FROM users
                WHERE phone = ?
                """,
                (
                    phone,
                ),
            ).fetchone()

            if not user:

                flash(
                    "Invalid phone number or password.",
                    "danger",
                )

                return render_template(
                    "login.html"
                )

            if not user["is_active"]:

                flash(
                    "Your account is inactive.",
                    "danger",
                )

                return render_template(
                    "login.html"
                )

            if not check_password_hash(
                user["password_hash"],
                password,
            ):

                flash(
                    "Invalid phone number or password.",
                    "danger",
                )

                return render_template(
                    "login.html"
                )

            conn.execute(
                """
                UPDATE users
                SET last_login = ?
                WHERE id = ?
                """,
                (
                    now_iso(),
                    user["id"],
                ),
            )

            conn.commit()

        finally:

            conn.close()

        session.clear()

        session[
            "user_id"
        ] = user["id"]

        return redirect(
            url_for("home")
        )

    return render_template(
        "login.html"
    )


# ============================================================
# OLD ADMIN LOGIN
# ============================================================

@app.before_request
def redirect_old_admin_login():

    if request.path == "/admin/login":

        return redirect(
            url_for("login")
        )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success",
    )

    return redirect(
        url_for("login")
    )


# ============================================================
# CASH IN / SAVE
# ============================================================

@app.route(
    "/cash-in",
    methods=["GET", "POST"],
)
@login_required
def cash_in():

    user = current_user()

    if request.method == "POST":

        plan_raw = request.form.get(
            "plan",
            request.form.get(
                "amount",
                "",
            ),
        ).strip()

        selected_plan = normalize_plan(
            plan_raw
        )

        if selected_plan not in ALLOWED_SAVE_PLANS:

            flash(
                (
                    "Please select a valid Save plan: "
                    "3,000 Frw or 6,000 Frw."
                ),
                "danger",
            )

            return render_template(
                "cash_in.html",
                user=user,
                payment_number=PAYMENT_NUMBER,
                plans=ALLOWED_SAVE_PLANS,
            )

        existing_plan = normalize_plan(
            user["save_plan"]
        )

        # ----------------------------------------------------
        # A user keeps one active plan.
        # This prevents changing reward/fee rules midway.
        # ----------------------------------------------------

        if existing_plan and existing_plan != selected_plan:

            flash(
                (
                    f"Your account is currently on "
                    f"{get_plan_name(existing_plan)}. "
                    "You cannot submit a different plan."
                ),
                "danger",
            )

            return redirect(
                url_for("cash_in")
            )

        # ----------------------------------------------------
        # PAYMENT PROOF
        # ----------------------------------------------------

        payment_proof = request.files.get(
            "payment_proof"
        )

        if not payment_proof or not payment_proof.filename:

            flash(
                "Please upload your MoMo payment screenshot.",
                "danger",
            )

            return redirect(
                url_for("cash_in")
            )

        original_filename = payment_proof.filename.strip()

        if "." not in original_filename:

            flash(
                "Please upload a valid image file.",
                "danger",
            )

            return redirect(
                url_for("cash_in")
            )

        extension = (
            original_filename.rsplit(".", 1)[1]
            .lower()
        )

        if extension not in ALLOWED_PAYMENT_PROOF_EXTENSIONS:

            flash(
                "Only JPG, JPEG, PNG, and WEBP images are allowed.",
                "danger",
            )

            return redirect(
                url_for("cash_in")
            )

        safe_original_filename = secure_filename(
            original_filename
        )

        if not safe_original_filename:

            flash(
                "The uploaded file name is invalid.",
                "danger",
            )

            return redirect(
                url_for("cash_in")
            )

        conn = get_db()

        saved_file_path = None

        try:

            # ------------------------------------------------
            # Create the pending Save request first so we have
            # its database ID for a unique proof filename.
            # ------------------------------------------------

            inserted = conn.execute(
                """
                INSERT INTO cash_ins
                (
                    user_id,
                    amount,
                    save_plan,
                    payment_number,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    user["id"],
                    selected_plan,
                    selected_plan,
                    PAYMENT_NUMBER,
                    "Pending",
                    now_iso(),
                ),
            ).fetchone()

            cash_in_id = inserted["id"]

            unique_filename = (
                f"cashin_{cash_in_id}_"
                f"{secrets.token_hex(8)}."
                f"{extension}"
            )

            saved_file_path = os.path.join(
                PAYMENT_PROOF_DIR,
                unique_filename,
            )

            payment_proof.save(
                saved_file_path
            )

            conn.execute(
                """
                UPDATE cash_ins
                SET payment_proof = ?
                WHERE id = ?
                """,
                (
                    unique_filename,
                    cash_in_id,
                ),
            )

            conn.execute(
                """
                INSERT INTO notifications
                (
                    user_id,
                    title,
                    message,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user["id"],
                    "Save Submitted",
                    (
                        f"Your {selected_plan:,} Frw "
                        f"{get_plan_name(selected_plan)} "
                        "Save request is pending admin "
                        "confirmation."
                    ),
                    now_iso(),
                ),
            )

            conn.commit()

        except Exception as error:

            conn.rollback()

            if saved_file_path and os.path.exists(
                saved_file_path
            ):
                try:
                    os.remove(
                        saved_file_path
                    )
                except Exception:
                    pass

            print(
                "SAVE SUBMISSION ERROR:",
                error,
            )

            flash(
                "Save request could not be submitted.",
                "danger",
            )

            return redirect(
                url_for("cash_in")
            )

        finally:

            conn.close()

        flash(
            (
                f"{selected_plan:,} Frw Save request "
                "submitted successfully. Your payment "
                "screenshot has been uploaded and is "
                "waiting for admin approval."
            ),
            "success",
        )

        return redirect(
            url_for("cash_in")
        )

    conn = get_db()

    try:

        cash_ins = conn.execute(
            """
            SELECT *
            FROM cash_ins
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (
                user["id"],
            ),
        ).fetchall()

    finally:

        conn.close()

    return render_template(
        "cash_in.html",
        user=user,
        payment_number=PAYMENT_NUMBER,
        cash_ins=cash_ins,
        plans=ALLOWED_SAVE_PLANS,
    )


# ============================================================
# CASH OUT / WITHDRAWAL
# ============================================================

@app.route(
    "/cash-out",
    methods=["GET", "POST"],
)
@login_required
def cash_out():

    user = current_user()

    plan = normalize_plan(
        user["save_plan"]
    )

    minimum_withdrawal = (
        get_min_withdrawal_for_plan(
            plan
        )
    )

    fee_percent = (
        get_withdrawal_fee_percent(
            plan
        )
    )

    if request.method == "POST":

        # ----------------------------------------------------
        # No withdrawal lock anymore.
        # ----------------------------------------------------

        if not plan:

            flash(
                (
                    "Please complete and get approval "
                    "for a Save plan before withdrawing."
                ),
                "danger",
            )

            return redirect(
                url_for("cash_out")
            )

        amount_raw = request.form.get(
            "amount",
            "",
        ).strip()

        network = request.form.get(
            "network",
            "",
        ).strip()

        phone = request.form.get(
            "phone",
            "",
        ).strip()

        try:

            amount = int(
                amount_raw
            )

        except (TypeError, ValueError):

            amount = 0

        if amount < minimum_withdrawal:

            flash(
                (
                    f"Minimum withdrawal for "
                    f"{get_plan_name(plan)} is "
                    f"{minimum_withdrawal:,} Frw."
                ),
                "danger",
            )

            return redirect(
                url_for("cash_out")
            )

        if network not in (
            "MTN",
            "Airtel",
        ):

            flash(
                "Please select MTN or Airtel.",
                "danger",
            )

            return redirect(
                url_for("cash_out")
            )

        if not phone:

            flash(
                "Destination phone number is required.",
                "danger",
            )

            return redirect(
                url_for("cash_out")
            )

        # Basic Rwanda phone validation.
        normalized_phone = (
            phone
            .replace(" ", "")
            .replace("-", "")
        )

        if normalized_phone.startswith(
            "+250"
        ):

            normalized_phone = (
                "0"
                + normalized_phone[4:]
            )

        if (
            not normalized_phone.isdigit()
            or len(normalized_phone) != 10
            or not normalized_phone.startswith("07")
        ):

            flash(
                "Please enter a valid Rwanda phone number.",
                "danger",
            )

            return redirect(
                url_for("cash_out")
            )

        if amount > user[
            "withdrawable_balance"
        ]:

            flash(
                (
                    "You cannot withdraw more than "
                    "your withdrawable balance."
                ),
                "danger",
            )

            return redirect(
                url_for("cash_out")
            )

        fee = calculate_withdrawal_fee(
            amount,
            plan,
        )

        net_amount = (
            amount - fee
        )

        if net_amount <= 0:

            flash(
                "The withdrawal amount is invalid.",
                "danger",
            )

            return redirect(
                url_for("cash_out")
            )

        conn = get_db()

        try:

            # ------------------------------------------------
            # Reserve the gross withdrawal amount.
            #
            # total_withdrawn is NOT increased yet.
            # It increases only after admin completion.
            # ------------------------------------------------

            updated = conn.execute(
                """
                UPDATE users
                SET
                    withdrawable_balance =
                        withdrawable_balance - ?

                WHERE id = ?

                AND withdrawable_balance >= ?
                """,
                (
                    amount,
                    user["id"],
                    amount,
                ),
            )

            if updated.rowcount != 1:

                conn.rollback()

                flash(
                    (
                        "Your balance changed before the "
                        "withdrawal could be submitted. "
                        "Please try again."
                    ),
                    "warning",
                )

                return redirect(
                    url_for("cash_out")
                )

            withdrawal_cursor = conn.execute(
                """
                INSERT INTO withdrawals
                (
                    user_id,
                    amount,
                    fee,
                    net_amount,
                    network,
                    phone,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    user["id"],
                    amount,
                    fee,
                    net_amount,
                    network,
                    normalized_phone,
                    "Pending",
                    now_iso(),
                ),
            )

            withdrawal_id = (
                withdrawal_cursor.fetchone()[
                    "id"
                ]
                if DATABASE_URL
                else None
            )

            # ------------------------------------------------
            # SQLite does not use RETURNING in this code path
            # ------------------------------------------------

            if not DATABASE_URL:

                withdrawal_id = conn.execute(
                    """
                    SELECT id
                    FROM withdrawals
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        user["id"],
                    ),
                ).fetchone()["id"]

            create_transaction(
                conn,
                user["id"],
                "WITHDRAWAL",
                amount,
                (
                    f"{network} withdrawal request "
                    f"of {amount:,} Frw. "
                    f"Fee: {fee:,} Frw. "
                    f"Net: {net_amount:,} Frw."
                ),
                status="Pending",
            )

            # Separate fee ledger entry for accounting.
            if fee > 0:

                create_transaction(
                    conn,
                    user["id"],
                    "WITHDRAWAL_FEE",
                    fee,
                    (
                        f"{fee_percent}% withdrawal fee "
                        f"for withdrawal #{withdrawal_id}."
                    ),
                    status="Pending",
                )

            conn.execute(
                """
                INSERT INTO notifications
                (
                    user_id,
                    title,
                    message,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user["id"],
                    "Withdrawal Submitted",
                    (
                        f"Requested: {amount:,} Frw. "
                        f"Fee: {fee:,} Frw. "
                        f"Net payout: {net_amount:,} Frw. "
                        "Your request is pending admin processing."
                    ),
                    now_iso(),
                ),
            )

            conn.commit()

        except Exception as error:

            conn.rollback()

            print(
                "WITHDRAWAL SUBMISSION ERROR:",
                error,
            )

            flash(
                "Withdrawal request could not be submitted.",
                "danger",
            )

            return redirect(
                url_for("cash_out")
            )

        finally:

            conn.close()

        flash(
            (
                f"Withdrawal submitted. "
                f"Requested {amount:,} Frw, "
                f"fee {fee:,} Frw, "
                f"net payout {net_amount:,} Frw."
            ),
            "success",
        )

        return redirect(
            url_for("cash_out")
        )

    conn = get_db()

    try:

        withdrawals = conn.execute(
            """
            SELECT *
            FROM withdrawals
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (
                user["id"],
            ),
        ).fetchall()

    finally:

        conn.close()

    return render_template(
        "cash_out.html",
        user=user,
        withdrawals=withdrawals,

        # Compatibility.
        lock_until=None,

        plan_name=get_plan_name(plan),
        minimum_withdrawal=minimum_withdrawal,
        withdrawal_fee_percent=fee_percent,
        fee_percent=fee_percent,
    )


# ============================================================
# DAILY ACTIVITIES
# ============================================================

@app.route("/activities")
@login_required
def activities():

    user = current_user()

    unlocked = has_saved_money(
        user["id"]
    )

    conn = get_db()

    try:

        activity_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE user_id = ?
            AND transaction_type IN
            (
                'VIDEO_REWARD',
                'TASK_REWARD'
            )
            AND status = 'Completed'
            """,
            (
                user["id"],
            ),
        ).fetchone()[0]

        unread_notifications = conn.execute(
            """
            SELECT COUNT(*)
            FROM notifications
            WHERE user_id = ?
            AND is_read = 0
            """,
            (
                user["id"],
            ),
        ).fetchone()[0]

    finally:

        conn.close()

    if not unlocked:

        return render_template(
            "home.html",
            user=user,
            activity=None,
            video=None,
            task=None,
            task_submission=None,
            unlocked=False,
            activity_count=activity_count,
            unread_notifications=unread_notifications,
            min_video_watch_seconds=MIN_VIDEO_WATCH_SECONDS,

            plan_name=get_plan_name(
                user["save_plan"]
            ),
            video_reward=0,
            task_reward=0,
            minimum_withdrawal=get_min_withdrawal_for_plan(
                user["save_plan"]
            ),
            withdrawal_fee_percent=get_withdrawal_fee_percent(
                user["save_plan"]
            ),
        )

    activity = get_or_create_daily_activity(
        user["id"]
    )

    conn = get_db()

    try:

        video = None
        task = None
        task_submission = None

        if activity and activity[
            "video_id"
        ]:

            video = conn.execute(
                """
                SELECT *
                FROM videos
                WHERE id = ?
                """,
                (
                    activity[
                        "video_id"
                    ],
                ),
            ).fetchone()

        if activity and activity[
            "task_id"
        ]:

            task = conn.execute(
                """
                SELECT *
                FROM tasks
                WHERE id = ?
                """,
                (
                    activity[
                        "task_id"
                    ],
                ),
            ).fetchone()

            task_submission = conn.execute(
                """
                SELECT *
                FROM task_submissions
                WHERE user_id = ?
                AND task_id = ?
                AND activity_date = ?
                """,
                (
                    user["id"],
                    activity[
                        "task_id"
                    ],
                    today_string(),
                ),
            ).fetchone()

    finally:

        conn.close()

    return render_template(
        "home.html",
        user=user,
        activity=activity,
        video=video,
        task=task,
        task_submission=task_submission,
        unlocked=True,
        activity_count=activity_count,
        unread_notifications=unread_notifications,
        min_video_watch_seconds=MIN_VIDEO_WATCH_SECONDS,

        plan_name=get_plan_name(
            user["save_plan"]
        ),
        video_reward=get_video_reward_for_plan(
            user["save_plan"]
        ),
        task_reward=get_task_reward_for_plan(
            user["save_plan"]
        ),
        minimum_withdrawal=get_min_withdrawal_for_plan(
            user["save_plan"]
        ),
        withdrawal_fee_percent=get_withdrawal_fee_percent(
            user["save_plan"]
        ),
    )


# ============================================================
# COMPLETE VIDEO
# ============================================================

@app.route(
    "/activities/video/confirm",
    methods=["POST"],
)
@login_required
def confirm_video():

    user = current_user()

    plan = normalize_plan(
        user["save_plan"]
    )

    if not has_saved_money(
        user["id"]
    ):

        return jsonify(
            {
                "success": False,
                "message": (
                    "Complete an approved Save first."
                ),
            }
        ), 403

    if not plan:

        return jsonify(
            {
                "success": False,
                "message": (
                    "Your account does not have an active Save plan."
                ),
            }
        ), 403

    reward = get_video_reward_for_plan(
        plan
    )

    if reward <= 0:

        return jsonify(
            {
                "success": False,
                "message": "Your Save plan is invalid.",
            }
        ), 403

    conn = get_db()

    try:

        # Prevent concurrent duplicate rewards.
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        activity = conn.execute(
            """
            SELECT *
            FROM daily_activities
            WHERE user_id = ?
            AND activity_date = ?
            """,
            (
                user["id"],
                today_string(),
            ),
        ).fetchone()

        if not activity:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Today's activity is not available."
                    ),
                }
            ), 404

        if activity[
            "video_completed"
        ]:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Today's video is already completed."
                    ),
                }
            ), 400

        if activity[
            "video_rewarded"
        ]:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Today's video reward was already given."
                    ),
                }
            ), 400

        video = conn.execute(
            """
            SELECT *
            FROM videos
            WHERE id = ?
            AND is_active = 1
            """,
            (
                activity[
                    "video_id"
                ],
            ),
        ).fetchone()

        if not video:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Today's video is unavailable."
                    ),
                }
            ), 404

        payload = request.get_json(
            silent=True
        ) or {}

        watch_seconds_raw = (
            request.form.get(
                "watch_seconds"
            )
            or payload.get(
                "watch_seconds",
                0,
            )
        )

        try:

            watch_seconds = int(
                watch_seconds_raw
            )

        except (TypeError, ValueError):

            watch_seconds = 0

        if watch_seconds < MIN_VIDEO_WATCH_SECONDS:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Please watch the video for at least "
                        f"{MIN_VIDEO_WATCH_SECONDS} seconds."
                    ),
                }
            ), 400

        updated = conn.execute(
            """
            UPDATE daily_activities
            SET
                video_completed = 1,
                video_rewarded = 1

            WHERE id = ?

            AND video_completed = 0
            AND video_rewarded = 0
            """,
            (
                activity["id"],
            ),
        )

        if updated.rowcount != 1:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Today's video reward has "
                        "already been processed."
                    ),
                }
            ), 400

        conn.execute(
            """
            UPDATE users
            SET
                withdrawable_balance =
                    withdrawable_balance + ?,

                total_earned =
                    total_earned + ?

            WHERE id = ?
            """,
            (
                reward,
                reward,
                user["id"],
            ),
        )

        create_transaction(
            conn,
            user["id"],
            "VIDEO_REWARD",
            reward,
            (
                f"Daily video reward - "
                f"{get_plan_name(plan)}"
            ),
            status="Completed",
        )

        conn.execute(
            """
            INSERT INTO notifications
            (
                user_id,
                title,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user["id"],
                "Video Reward",
                (
                    f"You earned {reward:,} Frw "
                    f"from today's video "
                    f"({get_plan_name(plan)})."
                ),
                now_iso(),
            ),
        )

        conn.commit()

        return jsonify(
            {
                "success": True,
                "reward": reward,
                "plan": plan,
                "message": (
                    f"Video completed. "
                    f"{reward:,} Frw added."
                ),
            }
        )

    except Exception as error:

        conn.rollback()

        print(
            "VIDEO REWARD ERROR:",
            error,
        )

        return jsonify(
            {
                "success": False,
                "message": (
                    "Video reward could not be processed."
                ),
            }
        ), 500

    finally:

        conn.close()


# ============================================================
# TASK SUBMISSION
# ============================================================

@app.route(
    "/activities/task/submit",
    methods=["POST"],
)
@login_required
def submit_task():

    user = current_user()

    plan = normalize_plan(
        user["save_plan"]
    )

    if not has_saved_money(
        user["id"]
    ):

        return jsonify(
            {
                "success": False,
                "message": (
                    "Complete an approved Save first."
                ),
            }
        ), 403

    if not plan:

        return jsonify(
            {
                "success": False,
                "message": (
                    "Your account does not have an active Save plan."
                ),
            }
        ), 403

    reward = get_task_reward_for_plan(
        plan
    )

    payload = request.get_json(
        silent=True
    ) or {}

    answer = (
        request.form.get("answer")
        or payload.get(
            "answer",
            "",
        )
    )

    answer = str(
        answer
    ).strip().upper()

    if answer not in (
        "A",
        "B",
        "C",
        "D",
    ):

        return jsonify(
            {
                "success": False,
                "message": (
                    "Please choose A, B, C or D."
                ),
            }
        ), 400

    conn = get_db()

    try:

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        date_value = today_string()

        activity = conn.execute(
            """
            SELECT *
            FROM daily_activities
            WHERE user_id = ?
            AND activity_date = ?
            """,
            (
                user["id"],
                date_value,
            ),
        ).fetchone()

        if not activity:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Today's task is not available."
                    ),
                }
            ), 404

        if not activity[
            "task_id"
        ]:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "No task is assigned today."
                    ),
                }
            ), 404

        if activity[
            "task_completed"
        ]:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Today's task is already completed."
                    ),
                }
            ), 400

        if activity[
            "task_rewarded"
        ]:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Today's task reward was already given."
                    ),
                }
            ), 400

        task = conn.execute(
            """
            SELECT *
            FROM tasks
            WHERE id = ?
            AND is_active = 1
            """,
            (
                activity[
                    "task_id"
                ],
            ),
        ).fetchone()

        if not task:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Today's task is unavailable."
                    ),
                }
            ), 404

        if (
            not task["option_a"]
            or not task["option_b"]
            or not task["option_c"]
            or not task["option_d"]
        ):

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "This task is not configured correctly."
                    ),
                }
            ), 500

        correct_answer = str(
            task["correct_answer"]
            or ""
        ).strip().upper()

        if correct_answer not in (
            "A",
            "B",
            "C",
            "D",
        ):

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "This task has an invalid correct answer."
                    ),
                }
            ), 500

        existing = conn.execute(
            """
            SELECT *
            FROM task_submissions
            WHERE user_id = ?
            AND task_id = ?
            AND activity_date = ?
            """,
            (
                user["id"],
                task["id"],
                date_value,
            ),
        ).fetchone()

        if existing:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "You have already answered today's task."
                    ),
                    "status": existing[
                        "status"
                    ],
                }
            ), 400

        is_correct = (
            answer == correct_answer
        )

        if is_correct:

            status = "Approved"

            reviewer_note = (
                "Automatically approved: correct answer."
            )

        else:

            reward = 0

            status = "Rejected"

            reviewer_note = (
                "Automatically rejected: incorrect answer."
            )

        conn.execute(
            """
            INSERT INTO task_submissions
            (
                user_id,
                task_id,
                activity_date,
                answer,
                status,
                submitted_at,
                reviewed_at,
                reviewer_note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                task["id"],
                date_value,
                answer,
                status,
                now_iso(),
                now_iso(),
                reviewer_note,
            ),
        )

        if is_correct:

            updated = conn.execute(
                """
                UPDATE daily_activities
                SET
                    task_completed = 1,
                    task_rewarded = 1

                WHERE id = ?

                AND task_completed = 0
                AND task_rewarded = 0
                """,
                (
                    activity["id"],
                ),
            )

            if updated.rowcount != 1:

                conn.rollback()

                return jsonify(
                    {
                        "success": False,
                        "message": (
                            "Task reward has already "
                            "been processed."
                        ),
                    }
                ), 400

            conn.execute(
                """
                UPDATE users
                SET
                    withdrawable_balance =
                        withdrawable_balance + ?,

                    total_earned =
                        total_earned + ?

                WHERE id = ?
                """,
                (
                    reward,
                    reward,
                    user["id"],
                ),
            )

            create_transaction(
                conn,
                user["id"],
                "TASK_REWARD",
                reward,
                (
                    f"Correct answer - daily task reward "
                    f"({get_plan_name(plan)})"
                ),
                status="Completed",
            )

            conn.execute(
                """
                INSERT INTO notifications
                (
                    user_id,
                    title,
                    message,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    user["id"],
                    "Task Reward",
                    (
                        f"Correct answer! You earned "
                        f"{reward:,} Frw from today's task."
                    ),
                    now_iso(),
                ),
            )

            conn.commit()

            return jsonify(
                {
                    "success": True,
                    "correct": True,
                    "reward": reward,
                    "status": "Approved",
                    "message": (
                        f"Correct answer! "
                        f"{reward:,} Frw has been added "
                        "to your withdrawable balance."
                    ),
                }
            )

        # ----------------------------------------------------
        # WRONG ANSWER
        # ----------------------------------------------------

        updated = conn.execute(
            """
            UPDATE daily_activities
            SET
                task_completed = 1,
                task_rewarded = 0

            WHERE id = ?

            AND task_completed = 0
            AND task_rewarded = 0
            """,
            (
                activity["id"],
            ),
        )

        if updated.rowcount != 1:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Today's task has already been processed."
                    ),
                }
            ), 400

        conn.execute(
            """
            INSERT INTO notifications
            (
                user_id,
                title,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user["id"],
                "Task Completed",
                (
                    "Your answer was incorrect. "
                    "No reward was added for today's task."
                ),
                now_iso(),
            ),
        )

        conn.commit()

        return jsonify(
            {
                "success": True,
                "correct": False,
                "reward": 0,
                "status": "Rejected",
                "message": (
                    "Incorrect answer. "
                    "No reward was added."
                ),
            }
        )

    except Exception as error:

        conn.rollback()

        print(
            "TASK PROCESSING ERROR:",
            error,
        )

        return jsonify(
            {
                "success": False,
                "message": (
                    "Task could not be processed."
                ),
            }
        ), 500

    finally:

        conn.close()


# ============================================================
# OLD TASK CONFIRM ENDPOINT
# ============================================================

@app.route(
    "/activities/task/confirm",
    methods=["POST"],
)
@login_required
def confirm_task():

    return submit_task()


# ============================================================
# ADMIN REQUIRED
# ============================================================

def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get(
            "admin_logged_in"
        ):

            return redirect(
                url_for("login")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


# ============================================================
# ADMIN SAVE REQUESTS
# ============================================================

@app.route(
    "/admin/save-requests",
    methods=["GET"],
)
@admin_required
def admin_save_requests():

    conn = get_db()

    try:

        save_requests = conn.execute(
            """
            SELECT
                ci.*,
                u.phone AS user_phone,
                u.save_plan AS user_save_plan
            FROM cash_ins ci
            JOIN users u
                ON u.id = ci.user_id
            ORDER BY ci.id DESC
            """
        ).fetchall()

    finally:

        conn.close()

    return render_template(
        "admin_save_requests.html",
        save_requests=save_requests,
    )


# ============================================================

# ============================================================
# ADMIN SAVE REQUEST ACTIONS
# ============================================================

@app.route("/admin/save-requests/<int:cash_in_id>/approve", methods=["POST"])
@admin_required
def approve_cash_in(cash_in_id):

    result = confirm_cash_in(cash_in_id)

    if isinstance(result, dict):
        if result.get("success"):
            return redirect(url_for("admin_save_requests"))

        return f"""
        <h2>Save Approval Failed</h2>
        <p>{result.get("message", "Unable to approve Save request.")}</p>
        <p><a href="{url_for("admin_save_requests")}">Back to Save Requests</a></p>
        """

    return redirect(url_for("admin_save_requests"))


@app.route("/admin/save-requests/<int:cash_in_id>/reject", methods=["POST"])
@admin_required
def reject_cash_in(cash_in_id):

    conn = get_db()

    try:
        cash_in = conn.execute(
            """
            SELECT *
            FROM cash_ins
            WHERE id = ?
            """,
            (cash_in_id,),
        ).fetchone()

        if not cash_in:
            return f"""
            <h2>Save Request Not Found</h2>
            <p><a href="{url_for("admin_save_requests")}">Back to Save Requests</a></p>
            """

        if str(cash_in["status"]).lower() != "pending":
            return f"""
            <h2>Request Already Processed</h2>
            <p>This Save request is no longer Pending.</p>
            <p><a href="{url_for("admin_save_requests")}">Back to Save Requests</a></p>
            """

        conn.execute(
            """
            UPDATE cash_ins
            SET status = 'Rejected',
                confirmed_at = ?
            WHERE id = ?
            """,
            (now_iso(), cash_in_id),
        )

        conn.execute(
            """
            INSERT INTO notifications
            (user_id, title, message, created_at, is_read)
            VALUES (?, ?, ?, ?, 0)
            """,
            (
                cash_in["user_id"],
                "Save Rejected",
                f"Your Save request of {cash_in['amount']} Frw was rejected after manual payment review.",
                now_iso(),
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return redirect(url_for("admin_save_requests"))


# ADMIN TASK SUBMISSIONS
# ============================================================

@app.route(
    "/admin/task-submissions",
    methods=["GET"],
)
@admin_required
def admin_task_submissions():

    conn = get_db()

    try:

        submissions = conn.execute(
            """
            SELECT
                ts.*,

                u.phone AS user_phone,

                u.save_plan AS user_save_plan,

                t.title AS task_title,

                t.reward AS task_reward

            FROM task_submissions ts

            JOIN users u
                ON u.id = ts.user_id

            JOIN tasks t
                ON t.id = ts.task_id

            ORDER BY ts.id DESC
            """
        ).fetchall()

    finally:

        conn.close()

    return render_template(
        "admin_task_submissions.html",
        submissions=submissions,
    )


# ============================================================
# ADMIN APPROVE TASK
# ============================================================

@app.route(
    "/admin/task-submissions/<int:submission_id>/approve",
    methods=["POST"],
)
@admin_required
def approve_task_submission(
    submission_id,
):

    conn = get_db()

    try:

        submission = conn.execute(
            """
            SELECT
                ts.*,

                u.phone AS user_phone,

                u.save_plan AS user_save_plan,

                t.reward AS task_reward

            FROM task_submissions ts

            JOIN tasks t
                ON t.id = ts.task_id

            JOIN users u
                ON u.id = ts.user_id

            WHERE ts.id = ?
            """,
            (
                submission_id,
            ),
        ).fetchone()

        if not submission:

            flash(
                "Task submission not found.",
                "danger",
            )

            return redirect(
                url_for(
                    "admin_task_submissions"
                )
            )

        if submission[
            "status"
        ] != "Pending":

            flash(
                "This submission has already been reviewed.",
                "warning",
            )

            return redirect(
                url_for(
                    "admin_task_submissions"
                )
            )

        plan = normalize_plan(
            submission[
                "user_save_plan"
            ]
        )

        reward = get_task_reward_for_plan(
            plan
        )

        if reward <= 0:

            flash(
                (
                    "User does not have a valid Save plan."
                ),
                "danger",
            )

            return redirect(
                url_for(
                    "admin_task_submissions"
                )
            )

        updated = conn.execute(
            """
            UPDATE daily_activities

            SET
                task_completed = 1,
                task_rewarded = 1

            WHERE user_id = ?
            AND task_id = ?
            AND activity_date = ?
            AND task_completed = 0
            AND task_rewarded = 0
            """,
            (
                submission[
                    "user_id"
                ],
                submission[
                    "task_id"
                ],
                submission[
                    "activity_date"
                ],
            ),
        )

        if updated.rowcount != 1:

            conn.rollback()

            flash(
                "Task reward has already been processed.",
                "warning",
            )

            return redirect(
                url_for(
                    "admin_task_submissions"
                )
            )

        conn.execute(
            """
            UPDATE users
            SET
                withdrawable_balance =
                    withdrawable_balance + ?,

                total_earned =
                    total_earned + ?

            WHERE id = ?
            """,
            (
                reward,
                reward,
                submission[
                    "user_id"
                ],
            ),
        )

        create_transaction(
            conn,
            submission[
                "user_id"
            ],
            "TASK_REWARD",
            reward,
            (
                "Approved daily task reward "
                f"({get_plan_name(plan)})"
            ),
            status="Completed",
        )

        conn.execute(
            """
            UPDATE task_submissions

            SET
                status = 'Approved',
                reviewed_at = ?,
                reviewer_note = ?

            WHERE id = ?
            AND status = 'Pending'
            """,
            (
                now_iso(),
                "Task approved by admin.",
                submission_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO notifications
            (
                user_id,
                title,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                submission[
                    "user_id"
                ],
                "Task Reward",
                (
                    f"Your task was approved. "
                    f"You earned {reward:,} Frw."
                ),
                now_iso(),
            ),
        )

        conn.commit()

        flash(
            (
                f"Task submission approved. "
                f"{reward:,} Frw awarded."
            ),
            "success",
        )

    except Exception as error:

        conn.rollback()

        print(
            "ADMIN TASK APPROVAL ERROR:",
            error,
        )

        flash(
            "Task approval failed.",
            "danger",
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin_task_submissions"
        )
    )


# ============================================================
# ADMIN REJECT TASK
# ============================================================

@app.route(
    "/admin/task-submissions/<int:submission_id>/reject",
    methods=["POST"],
)
@admin_required
def reject_task_submission(
    submission_id,
):

    conn = get_db()

    try:

        submission = conn.execute(
            """
            SELECT *
            FROM task_submissions
            WHERE id = ?
            """,
            (
                submission_id,
            ),
        ).fetchone()

        if not submission:

            flash(
                "Task submission not found.",
                "danger",
            )

            return redirect(
                url_for(
                    "admin_task_submissions"
                )
            )

        if submission[
            "status"
        ] != "Pending":

            flash(
                "This submission has already been reviewed.",
                "warning",
            )

            return redirect(
                url_for(
                    "admin_task_submissions"
                )
            )

        reviewer_note = request.form.get(
            "reviewer_note",
            "Task submission rejected.",
        ).strip()

        if not reviewer_note:

            reviewer_note = (
                "Task submission rejected."
            )

        conn.execute(
            """
            UPDATE task_submissions

            SET
                status = 'Rejected',
                reviewed_at = ?,
                reviewer_note = ?

            WHERE id = ?
            AND status = 'Pending'
            """,
            (
                now_iso(),
                reviewer_note,
                submission_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO notifications
            (
                user_id,
                title,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                submission[
                    "user_id"
                ],
                "Task Submission Rejected",
                (
                    "Your daily task submission was rejected. "
                    + reviewer_note
                ),
                now_iso(),
            ),
        )

        conn.commit()

        flash(
            "Task submission rejected.",
            "success",
        )

    except Exception as error:

        conn.rollback()

        print(
            "ADMIN TASK REJECTION ERROR:",
            error,
        )

        flash(
            "Task rejection failed.",
            "danger",
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin_task_submissions"
        )
    )


# ============================================================
# PROFILE
# ============================================================

@app.route("/profile")
@login_required
def profile():

    user = current_user()

    conn = get_db()

    try:

        referral_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM referrals
            WHERE referrer_id = ?
            """,
            (
                user["id"],
            ),
        ).fetchone()[0]

        referral_earnings = conn.execute(
            """
            SELECT COALESCE(
                SUM(amount),
                0
            )
            FROM transactions
            WHERE user_id = ?
            AND transaction_type = 'REFERRAL_BONUS'
            AND status = 'Completed'
            """,
            (
                user["id"],
            ),
        ).fetchone()[0]

    finally:

        conn.close()

    referral_link = (
        request.host_url.rstrip("/")
        + "/register?ref="
        + user["referral_code"]
    )

    plan = normalize_plan(
        user["save_plan"]
    )

    return render_template(
        "profile.html",
        user=user,
        referral_count=referral_count,
        referral_earnings=referral_earnings,
        referral_link=referral_link,

        plan_name=get_plan_name(
            plan
        ),
        video_reward=get_video_reward_for_plan(
            plan
        ),
        task_reward=get_task_reward_for_plan(
            plan
        ),
        minimum_withdrawal=get_min_withdrawal_for_plan(
            plan
        ),
        withdrawal_fee_percent=get_withdrawal_fee_percent(
            plan
        ),
    )


# ============================================================
# CHANGE PASSWORD
# ============================================================

@app.route(
    "/change-password",
    methods=["GET", "POST"],
)
@login_required
def change_password():

    user = current_user()

    if request.method == "POST":

        current_password = request.form.get(
            "current_password",
            "",
        )

        new_password = request.form.get(
            "new_password",
            "",
        )

        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        if not check_password_hash(
            user["password_hash"],
            current_password,
        ):

            flash(
                "Current password is incorrect.",
                "danger",
            )

            return render_template(
                "change_password.html"
            )

        if len(new_password) < 6:

            flash(
                (
                    "New password must contain "
                    "at least 6 characters."
                ),
                "danger",
            )

            return render_template(
                "change_password.html"
            )

        if new_password != confirm_password:

            flash(
                "New passwords do not match.",
                "danger",
            )

            return render_template(
                "change_password.html"
            )

        new_hash = generate_password_hash(
            new_password
        )

        conn = get_db()

        try:

            conn.execute(
                """
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
                """,
                (
                    new_hash,
                    user["id"],
                ),
            )

            conn.commit()

        finally:

            conn.close()

        flash(
            "Password changed successfully.",
            "success",
        )

        return redirect(
            url_for("profile")
        )

    return render_template(
        "change_password.html"
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.route("/notifications")
@login_required
def notifications():

    user = current_user()

    conn = get_db()

    try:

        notifications_list = conn.execute(
            """
            SELECT *
            FROM notifications
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 50
            """,
            (
                user["id"],
            ),
        ).fetchall()

        conn.execute(
            """
            UPDATE notifications
            SET is_read = 1
            WHERE user_id = ?
            """,
            (
                user["id"],
            ),
        )

        conn.commit()

    finally:

        conn.close()

    return render_template(
        "notifications.html",
        user=user,
        notifications=notifications_list,
    )


# ============================================================
# NOTIFICATION API
# ============================================================

@app.route("/api/notifications")
@login_required
def api_notifications():

    user = current_user()

    conn = get_db()

    try:

        rows = conn.execute(
            """
            SELECT
                id,
                title,
                message,
                is_read,
                created_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 50
            """,
            (
                user["id"],
            ),
        ).fetchall()

        unread = conn.execute(
            """
            SELECT COUNT(*)
            FROM notifications
            WHERE user_id = ?
            AND is_read = 0
            """,
            (
                user["id"],
            ),
        ).fetchone()[0]

    finally:

        conn.close()

    return jsonify(
        {
            "success": True,
            "unread_count": unread,
            "notifications": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "message": row["message"],
                    "is_read": bool(
                        row["is_read"]
                    ),
                    "created_at": row[
                        "created_at"
                    ],
                }
                for row in rows
            ],
        }
    )


# ============================================================
# HELP CENTER
# ============================================================

@app.route("/help-center")
@login_required
def help_center():

    user = current_user()

    return render_template(
        "help_center.html",
        user=user,
    )


# ============================================================
# API - CURRENT USER
# ============================================================

@app.route("/api/me")
@login_required
def api_me():

    user = current_user()

    conn = get_db()

    try:

        referral_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM referrals
            WHERE referrer_id = ?
            """,
            (
                user["id"],
            ),
        ).fetchone()[0]

        referral_earnings = conn.execute(
            """
            SELECT COALESCE(
                SUM(amount),
                0
            )
            FROM transactions
            WHERE user_id = ?
            AND transaction_type = 'REFERRAL_BONUS'
            AND status = 'Completed'
            """,
            (
                user["id"],
            ),
        ).fetchone()[0]

    finally:

        conn.close()

    plan = normalize_plan(
        user["save_plan"]
    )

    return jsonify(
        {
            "success": True,

            "user": {
                "id": user["id"],
                "phone": user["phone"],

                "save_plan": plan,

                "plan_name": get_plan_name(
                    plan
                ),

                "saved_balance": user[
                    "saved_balance"
                ],

                "withdrawable_balance": user[
                    "withdrawable_balance"
                ],

                "total_earned": user[
                    "total_earned"
                ],

                "total_withdrawn": user[
                    "total_withdrawn"
                ],

                "registration_bonus": user[
                    "registration_bonus"
                ],

                "video_reward": get_video_reward_for_plan(
                    plan
                ),

                "task_reward": get_task_reward_for_plan(
                    plan
                ),

                "minimum_withdrawal": get_min_withdrawal_for_plan(
                    plan
                ),

                "withdrawal_fee_percent": get_withdrawal_fee_percent(
                    plan
                ),

                "referral_code": user[
                    "referral_code"
                ],

                "referral_count": referral_count,

                "referral_earnings": referral_earnings,
            },
        }
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return (
        render_template(
            "login.html",
            error="Page not found.",
        ),
        404,
    )


@app.errorhandler(500)
def internal_error(error):

    print(
        "GLOBAL 500 ERROR:",
        error,
    )

    return (
        "KoraCash server error.",
        500,
    )


# ============================================================
# ADMIN BLUEPRINT
# ============================================================

from admin import admin_bp

app.register_blueprint(
    admin_bp
)


# ============================================================
# STARTUP
# ============================================================

init_db()


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )