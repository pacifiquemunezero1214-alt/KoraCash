import os
import sqlite3
import psycopg
from psycopg.rows import dict_row
import secrets
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

from dotenv import load_dotenv


# ============================================================
# KoraCash
# User + Admin Unified Login
# Automatic Daily Activity Engine
# ============================================================

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "koracash.db")
DATABASE_URL = os.getenv("DATABASE_URL")

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "KORACASH_SECRET_KEY",
    "koracash-development-secret-change-later",
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ============================================================
# CONSTANTS
# ============================================================

REGISTRATION_BONUS = 1500
REFERRAL_BONUS = 1500

REFERRAL_REQUIRED_SAVE = 3000

VIDEO_REWARD = 1000
TASK_REWARD = 1000

PAYMENT_NUMBER = "0798386664"

WITHDRAWAL_LOCK_DAYS = 3

MIN_VIDEO_WATCH_SECONDS = 30

TASK_ROTATION_DAYS = 4


# ============================================================
# DATABASE
# ============================================================

class HybridRow(dict):

    def __getitem__(self, key):

        if isinstance(key, int):
            return list(self.values())[key]

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
                    [column[0] for column in self.cursor.description],
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
        return getattr(self.cursor, name)


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

        sql = sql.replace(
            "date(?, ?)",
            "(CAST(? AS DATE) + CAST(? AS INTEGER))",
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
            cursor = self.connection.execute(sql)
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
            WHERE table_name = %s
            """,
            (table_name,),
        ).fetchall()
    else:
        columns = conn.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()

    existing_columns = {
        column["column_name"] if DATABASE_URL else column["name"]
        for column in columns
    }

    if column_name not in existing_columns:
        conn.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {definition}
            """
        )

def init_db():

    conn = get_db()

    if DATABASE_URL:

        # --------------------------------------------------------
        # NEON / POSTGRESQL
        #
        # Tables were already created and data was migrated.
        # Do NOT run SQLite executescript() here.
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

        seed_content(conn)

        conn.commit()
        conn.close()

        return

    # --------------------------------------------------------
    # SQLITE
    # --------------------------------------------------------

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            referral_code TEXT UNIQUE NOT NULL,
            referred_by INTEGER,

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

            reward INTEGER NOT NULL DEFAULT 1000,

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

            reward INTEGER NOT NULL DEFAULT 1000,

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
        """
    )

    # --------------------------------------------------------
    # Older database migrations
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

    seed_content(conn)

    conn.commit()
    conn.close()

# ============================================================
# TIME HELPERS
# ============================================================

def now_utc():
    return datetime.now(timezone.utc)


def now_iso():
    return now_utc().isoformat()


def today_string():
    rwanda_time = datetime.now(
        ZoneInfo("Africa/Kigali")
    )

    return rwanda_time.strftime("%Y-%m-%d")


# ============================================================
# SEED CONTENT
# ============================================================

def seed_content(conn):

    video_count = conn.execute(
        "SELECT COUNT(*) AS count FROM videos"
    ).fetchone()["count"]

    task_count = conn.execute(
        "SELECT COUNT(*) AS count FROM tasks"
    ).fetchone()["count"]

    now = now_iso()

    # Only seed placeholders if library is completely empty.
    if video_count == 0:

        videos = [
            (
                "Daily Video 1",
                "Watch today's KoraCash learning video.",
                "https://example.com/video1",
                VIDEO_REWARD,
                now,
            ),
            (
                "Daily Video 2",
                "Watch today's KoraCash learning video.",
                "https://example.com/video2",
                VIDEO_REWARD,
                now,
            ),
            (
                "Daily Video 3",
                "Watch today's KoraCash learning video.",
                "https://example.com/video3",
                VIDEO_REWARD,
                now,
            ),
            (
                "Daily Video 4",
                "Watch today's KoraCash learning video.",
                "https://example.com/video4",
                VIDEO_REWARD,
                now,
            ),
            (
                "Daily Video 5",
                "Watch today's KoraCash learning video.",
                "https://example.com/video5",
                VIDEO_REWARD,
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

    # Only seed placeholders if task library is completely empty.
    if task_count == 0:

        tasks = [
            (
                "Daily Task 1",
                "Complete today's task.",
                TASK_REWARD,
                now,
            ),
            (
                "Daily Task 2",
                "Complete today's task.",
                TASK_REWARD,
                now,
            ),
            (
                "Daily Task 3",
                "Complete today's task.",
                TASK_REWARD,
                now,
            ),
            (
                "Daily Task 4",
                "Complete today's task.",
                TASK_REWARD,
                now,
            ),
            (
                "Daily Task 5",
                "Complete today's task.",
                TASK_REWARD,
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

    user_id = session.get("user_id")

    if not user_id:
        return None

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    conn.close()

    return user


def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get("user_id"):

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

        return view(*args, **kwargs)

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
# TRANSACTIONS
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
            amount,
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

        exists = conn.execute(
            """
            SELECT id
            FROM users
            WHERE referral_code = ?
            """,
            (code,),
        ).fetchone()

        conn.close()

        if not exists:
            return code


# ============================================================
# DAILY ACTIVITY HELPERS
# ============================================================

def get_valid_video(conn, video_id):

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
        (video_id,),
    ).fetchone()


def get_valid_task(conn, task_id):

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
        AND TRIM(correct_answer) IN ('A', 'B', 'C', 'D', 'a', 'b', 'c', 'd')
        """,
        (task_id,),
    ).fetchone()


def choose_daily_video(conn, user_id, date_value):

    video = conn.execute(
        """
        SELECT *
        FROM videos
        WHERE is_active = 1
        AND video_url IS NOT NULL
        AND TRIM(video_url) != ''

        AND id NOT IN
        (
            SELECT video_id
            FROM daily_activities
            WHERE user_id = ?
            AND video_id IS NOT NULL
            AND CAST(activity_date AS DATE) >= CAST(? AS DATE) + CAST(? AS INTERVAL)
        )

        ORDER BY RANDOM()
        LIMIT 1
        """,
        (
            user_id,
            date_value,
            f"-{TASK_ROTATION_DAYS} days",
        ),
    ).fetchone()

    if video:
        return video

    return conn.execute(
        """
        SELECT *
        FROM videos
        WHERE is_active = 1
        AND video_url IS NOT NULL
        AND TRIM(video_url) != ''
        ORDER BY RANDOM()
        LIMIT 1
        """
    ).fetchone()


def choose_daily_task(conn, user_id, date_value):

    task = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE is_active = 1

        AND option_a IS NOT NULL
        AND option_b IS NOT NULL
        AND option_c IS NOT NULL
        AND option_d IS NOT NULL

        AND correct_answer IS NOT NULL

        AND TRIM(correct_answer) IN
        (
            'A',
            'B',
            'C',
            'D',
            'a',
            'b',
            'c',
            'd'
        )

        AND id NOT IN
        (
            SELECT task_id
            FROM daily_activities
            WHERE user_id = ?
            AND task_id IS NOT NULL
            AND CAST(activity_date AS DATE) >= CAST(? AS DATE) + CAST(? AS INTERVAL)
        )

        ORDER BY RANDOM()
        LIMIT 1
        """,
        (
            user_id,
            date_value,
            f"-{TASK_ROTATION_DAYS} days",
        ),
    ).fetchone()

    if task:
        return task

    return conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE is_active = 1

        AND option_a IS NOT NULL
        AND option_b IS NOT NULL
        AND option_c IS NOT NULL
        AND option_d IS NOT NULL

        AND correct_answer IS NOT NULL

        AND TRIM(correct_answer) IN
        (
            'A',
            'B',
            'C',
            'D',
            'a',
            'b',
            'c',
            'd'
        )

        ORDER BY RANDOM()
        LIMIT 1
        """
    ).fetchone()


# ============================================================
# DAILY ACTIVITY ENGINE
#
# IMPORTANT FIX:
# Existing daily activity is checked again.
# Old/inactive task or video is replaced automatically.
# ============================================================

def get_or_create_daily_activity(user_id):

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

        # ----------------------------------------------------
        # Existing activity
        # ----------------------------------------------------

        if activity:

            current_video = get_valid_video(
                conn,
                activity["video_id"],
            )

            current_task = get_valid_task(
                conn,
                activity["task_id"],
            )

            new_video_id = activity["video_id"]
            new_task_id = activity["task_id"]

            changed = False

            # ------------------------------------------------
            # Replace old/inactive video
            # ------------------------------------------------

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

                if new_video_id != activity["video_id"]:
                    changed = True

            # ------------------------------------------------
            # Replace old/invalid task
            # ------------------------------------------------

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

                if new_task_id != activity["task_id"]:
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
                    (activity["id"],),
                ).fetchone()

            return activity

        # ----------------------------------------------------
        # No activity yet: create one
        # ----------------------------------------------------

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

        except sqlite3.IntegrityError:

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
# SAVED MONEY
# ============================================================

def has_saved_money(user_id):

    conn = get_db()

    row = conn.execute(
        """
        SELECT saved_balance
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    conn.close()

    return bool(
        row
        and row["saved_balance"] > 0
    )


# ============================================================
# WITHDRAWAL LOCK
# ============================================================

def get_withdrawal_lock(user):

    lock_value = user[
        "withdrawal_locked_until"
    ]

    if not lock_value:
        return None

    try:

        lock_date = datetime.fromisoformat(
            lock_value
        )

    except ValueError:

        return None

    if lock_date.tzinfo is None:

        lock_date = lock_date.replace(
            tzinfo=timezone.utc
        )

    if now_utc() >= lock_date:

        return None

    return lock_date


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
        (referred_user_id,),
    ).fetchone()

    if not referral:
        return False

    referrer = conn.execute(
        """
        SELECT id, phone, is_active
        FROM users
        WHERE id = ?
        """,
        (referral["referrer_id"],),
    ).fetchone()

    if not referrer:
        return False

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
            REFERRAL_BONUS,
            REFERRAL_BONUS,
            referral["referrer_id"],
        ),
    )

    create_transaction(
        conn,
        referral["referrer_id"],
        "REFERRAL_BONUS",
        REFERRAL_BONUS,
        (
            "Referral bonus because referred user "
            "completed a confirmed Save of at least "
            f"{REFERRAL_REQUIRED_SAVE:,} Frw."
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
                f"You received {REFERRAL_BONUS:,} Frw referral "
                "bonus because your referred user completed "
                "a confirmed Save."
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
            (cash_in_id,),
        ).fetchone()

        if not cash_in:

            return {
                "success": False,
                "message": "Cash In request not found.",
            }

        if cash_in["status"] == "Completed":

            return {
                "success": False,
                "message": "Cash In has already been confirmed.",
            }

        if cash_in["status"] != "Pending":

            return {
                "success": False,
                "message": "Cash In cannot be confirmed.",
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

        if amount <= 0:

            return {
                "success": False,
                "message": (
                    "Confirmation amount must be "
                    "greater than zero."
                ),
            }

        user_id = cash_in["user_id"]

        updated = conn.execute(
            """
            UPDATE cash_ins
            SET
                amount = ?,
                status = 'Completed',
                confirmed_at = ?

            WHERE id = ?
            AND status = 'Pending'
            """,
            (
                amount,
                now_iso(),
                cash_in_id,
            ),
        )

        if updated.rowcount != 1:

            conn.rollback()

            return {
                "success": False,
                "message": "Cash In has already been processed.",
            }

        conn.execute(
            """
            UPDATE users
            SET
                saved_balance =
                    saved_balance + ?

            WHERE id = ?
            """,
            (
                amount,
                user_id,
            ),
        )

        create_transaction(
            conn,
            user_id,
            "CASH_IN",
            amount,
            "Confirmed Save / Cash In",
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
                "Save Confirmed",
                (
                    f"Your Save of {amount:,} Frw has been "
                    "confirmed and added to your Saved Balance."
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
            "referral_rewarded": referral_rewarded,
            "message": "Cash In confirmed successfully.",
        }

    except Exception as error:

        conn.rollback()

        return {
            "success": False,
            "message": "Cash In confirmation failed.",
            "error": str(error),
        }

    finally:

        conn.close()


# ============================================================
# INDEX
# ============================================================

@app.route("/")
def index():

    if session.get("admin_logged_in"):

        return redirect(
            url_for("admin.admin_dashboard")
        )

    if session.get("user_id"):

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

        if activity and activity["video_id"]:

            video = conn.execute(
                """
                SELECT *
                FROM videos
                WHERE id = ?
                """,
                (
                    activity["video_id"],
                ),
            ).fetchone()

        if activity and activity["task_id"]:

            task = conn.execute(
                """
                SELECT *
                FROM tasks
                WHERE id = ?
                """,
                (
                    activity["task_id"],
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
                    activity["task_id"],
                    today_string(),
                ),
            ).fetchone()

        conn.close()

    conn = get_db()

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
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"],
)
def register():

    if session.get("admin_logged_in"):

        return redirect(
            url_for("admin.admin_dashboard")
        )

    if session.get("user_id"):

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

        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        referral_code = request.form.get(
            "referral_code",
            "",
        ).strip().upper()

        if not phone:

            flash(
                "Phone number is required.",
                "danger",
            )

            return render_template(
                "register.html"
            )

        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "danger",
            )

            return render_template(
                "register.html"
            )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger",
            )

            return render_template(
                "register.html"
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
                    "register.html"
                )

            referrer = None

            if referral_code:

                referrer = conn.execute(
                    """
                    SELECT id, phone, referral_code
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
                        "register.html"
                    )

                if referrer["phone"] == phone:

                    flash(
                        "You cannot use your own referral code.",
                        "danger",
                    )

                    return render_template(
                        "register.html"
                    )

            user_referral_code = generate_referral_code()

            password_hash = generate_password_hash(
                password
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
                        withdrawable_balance,
                        total_earned,
                        registration_bonus,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                        REGISTRATION_BONUS,
                        REGISTRATION_BONUS,
                        REGISTRATION_BONUS,
                        created_at,
                    ),
                )

                user_id = cursor.fetchone()["id"]

            else:

                cursor = conn.execute(
                    """
                    INSERT INTO users
                    (
                        phone,
                        password_hash,
                        referral_code,
                        referred_by,
                        withdrawable_balance,
                        total_earned,
                        registration_bonus,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                        "registration bonus."
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
                            "A new user joined using your referral "
                            "link. You will receive "
                            f"{REFERRAL_BONUS:,} Frw after their "
                            "confirmed Save reaches "
                            f"{REFERRAL_REQUIRED_SAVE:,} Frw."
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
                "Registration could not be completed. Please try again.",
                "danger",
            )

            return render_template(
                "register.html"
            )

        finally:

            conn.close()

        flash(
            "Registration successful. You received 1,500 Frw.",
            "success",
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# ============================================================
# UNIFIED LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"],
)
def login():

    if session.get("admin_logged_in"):

        return redirect(
            url_for("admin.admin_dashboard")
        )

    if session.get("user_id"):

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

            session["admin_logged_in"] = True
            session["admin_phone"] = phone

            return redirect(
                url_for("admin.admin_dashboard")
            )

        # ----------------------------------------------------
        # NORMAL USER LOGIN
        # ----------------------------------------------------

        conn = get_db()

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

            conn.close()

            flash(
                "Invalid phone number or password.",
                "danger",
            )

            return render_template(
                "login.html"
            )

        if not user["is_active"]:

            conn.close()

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

            conn.close()

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
        conn.close()

        session.clear()

        session["user_id"] = user["id"]

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
# CASH IN
# ============================================================

@app.route(
    "/cash-in",
    methods=["GET", "POST"],
)
@login_required
def cash_in():

    user = current_user()

    if request.method == "POST":

        amount_raw = request.form.get(
            "amount",
            "",
        ).strip()

        try:
            amount = int(amount_raw)
        except (TypeError, ValueError):
            amount = 0

        if amount < 100:

            flash(
                "Minimum Cash In amount is 100 Frw.",
                "danger",
            )

            return render_template(
                "cash_in.html",
                user=user,
                payment_number=PAYMENT_NUMBER,
            )

        conn = get_db()

        try:

            conn.execute(
                """
                INSERT INTO cash_ins
                (
                    user_id,
                    amount,
                    payment_number,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    amount,
                    PAYMENT_NUMBER,
                    "Pending",
                    now_iso(),
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
                    "Cash In Submitted",
                    (
                        f"Your Cash In request of {amount:,} Frw "
                        "is pending confirmation."
                    ),
                    now_iso(),
                ),
            )

            conn.commit()

        except Exception:

            conn.rollback()

            flash(
                "Cash In request could not be submitted.",
                "danger",
            )

            return redirect(
                url_for("cash_in")
            )

        finally:

            conn.close()

        flash(
            (
                "Cash In request submitted. Complete the payment "
                "and wait for confirmation."
            ),
            "success",
        )

        return redirect(
            url_for("cash_in")
        )

    conn = get_db()

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

    conn.close()

    return render_template(
        "cash_in.html",
        user=user,
        payment_number=PAYMENT_NUMBER,
        cash_ins=cash_ins,
    )


# ============================================================
# CASH OUT
# ============================================================

@app.route(
    "/cash-out",
    methods=["GET", "POST"],
)
@login_required
def cash_out():

    user = current_user()

    lock_until = get_withdrawal_lock(user)

    if request.method == "POST":

        if lock_until:

            remaining = (
                lock_until - now_utc()
            )

            days = remaining.days

            hours = (
                remaining.seconds // 3600
            )

            minutes = (
                (remaining.seconds % 3600)
                // 60
            )

            flash(
                (
                    "Withdrawal locked. Time remaining: "
                    f"{days}d {hours}h {minutes}m."
                ),
                "warning",
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
            amount = int(amount_raw)
        except (TypeError, ValueError):
            amount = 0

        if amount <= 0:

            flash(
                "Enter a valid withdrawal amount.",
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

        if amount > user["withdrawable_balance"]:

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

        conn = get_db()

        try:

            new_lock = (
                now_utc()
                + timedelta(
                    days=WITHDRAWAL_LOCK_DAYS
                )
            )

            conn.execute(
                """
                UPDATE users
                SET
                    withdrawable_balance =
                        withdrawable_balance - ?,

                    total_withdrawn =
                        total_withdrawn + ?,

                    withdrawal_locked_until = ?

                WHERE id = ?
                """,
                (
                    amount,
                    amount,
                    new_lock.isoformat(),
                    user["id"],
                ),
            )

            conn.execute(
                """
                INSERT INTO withdrawals
                (
                    user_id,
                    amount,
                    network,
                    phone,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    amount,
                    network,
                    phone,
                    "Pending",
                    now_iso(),
                ),
            )

            create_transaction(
                conn,
                user["id"],
                "WITHDRAWAL",
                amount,
                f"{network} withdrawal to {phone}",
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
                        f"Your {amount:,} Frw withdrawal "
                        "request is pending."
                    ),
                    now_iso(),
                ),
            )

            conn.commit()

        except Exception:

            conn.rollback()

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
            "Withdrawal request submitted successfully.",
            "success",
        )

        return redirect(
            url_for("cash_out")
        )

    conn = get_db()

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

    conn.close()

    return render_template(
        "cash_out.html",
        user=user,
        withdrawals=withdrawals,
        lock_until=lock_until,
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
        )

    activity = get_or_create_daily_activity(
        user["id"]
    )

    conn = get_db()

    video = None
    task = None
    task_submission = None

    if activity and activity["video_id"]:

        video = conn.execute(
            """
            SELECT *
            FROM videos
            WHERE id = ?
            """,
            (
                activity["video_id"],
            ),
        ).fetchone()

    if activity and activity["task_id"]:

        task = conn.execute(
            """
            SELECT *
            FROM tasks
            WHERE id = ?
            """,
            (
                activity["task_id"],
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
                activity["task_id"],
                today_string(),
            ),
        ).fetchone()

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

    if not has_saved_money(user["id"]):

        return jsonify(
            {
                "success": False,
                "message": "Complete a Cash In first.",
            }
        ), 403

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
                user["id"],
                today_string(),
            ),
        ).fetchone()

        if not activity:

            return jsonify(
                {
                    "success": False,
                    "message": "Today's activity is not available.",
                }
            ), 404

        if activity["video_completed"]:

            return jsonify(
                {
                    "success": False,
                    "message": "Today's video is already completed.",
                }
            ), 400

        if activity["video_rewarded"]:

            return jsonify(
                {
                    "success": False,
                    "message": "Today's video reward was already given.",
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
                activity["video_id"],
            ),
        ).fetchone()

        if not video:

            return jsonify(
                {
                    "success": False,
                    "message": "Today's video is unavailable.",
                }
            ), 404

        # ----------------------------------------------------
        # Accept form OR JSON
        # ----------------------------------------------------

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

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Please watch the video for at least "
                        f"{MIN_VIDEO_WATCH_SECONDS} seconds."
                    ),
                }
            ), 400

        reward = int(
            video["reward"]
            or VIDEO_REWARD
        )

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
                        "Today's video reward has already "
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
            "VIDEO_REWARD",
            reward,
            "Daily video reward",
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
                    "from today's video."
                ),
                now_iso(),
            ),
        )

        conn.commit()

        return jsonify(
            {
                "success": True,
                "reward": reward,
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
# AUTOMATIC MULTIPLE-CHOICE TASK ENGINE
# ============================================================

@app.route(
    "/activities/task/submit",
    methods=["POST"],
)
@login_required
def submit_task():

    user = current_user()

    if not has_saved_money(user["id"]):

        return jsonify(
            {
                "success": False,
                "message": "Complete a Cash In first.",
            }
        ), 403

    # --------------------------------------------------------
    # IMPORTANT:
    # Accept both HTML form and JSON.
    # --------------------------------------------------------

    payload = request.get_json(
        silent=True
    ) or {}

    answer = (
        request.form.get("answer")
        or payload.get("answer", "")
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

        if not activity["task_id"]:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "No task is assigned today."
                    ),
                }
            ), 404

        if activity["task_completed"]:

            conn.rollback()

            return jsonify(
                {
                    "success": False,
                    "message": (
                        "Today's task is already completed."
                    ),
                }
            ), 400

        if activity["task_rewarded"]:

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
                activity["task_id"],
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

        if not task["option_a"] or not task["option_b"] \
                or not task["option_c"] or not task["option_d"]:

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
            task["correct_answer"] or ""
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
                    "status": existing["status"],
                }
            ), 400

        is_correct = (
            answer == correct_answer
        )

        if is_correct:

            reward = int(
                task["reward"]
                or TASK_REWARD
            )

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

        # ----------------------------------------------------
        # Store submission
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # CORRECT ANSWER
        # ----------------------------------------------------

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
                            "Task reward has already been processed."
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
                "Correct answer - daily task reward",
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

    except (sqlite3.IntegrityError, psycopg.errors.UniqueViolation) as error:

        conn.rollback()

        print(
            "TASK INTEGRITY ERROR:",
            error,
        )

        return jsonify(
            {
                "success": False,
                "message": (
                    "You have already answered today's task."
                ),
            }
        ), 400

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
                "error": str(error),
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

        if not session.get("admin_logged_in"):

            return redirect(
                url_for("login")
            )

        return view(*args, **kwargs)

    return wrapped


# ============================================================
# ADMIN TASK SUBMISSIONS
# ============================================================

@app.route(
    "/admin/task-submissions",
    methods=["GET"],
)
@admin_required
def admin_task_submissions():

    conn = get_db()

    submissions = conn.execute(
        """
        SELECT
            ts.*,

            u.phone AS user_phone,

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
                t.reward AS task_reward,
                u.phone AS user_phone

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
                url_for("admin_task_submissions")
            )

        if submission["status"] != "Pending":

            flash(
                "This submission has already been reviewed.",
                "warning",
            )

            return redirect(
                url_for("admin_task_submissions")
            )

        reward = int(
            submission["task_reward"]
            or TASK_REWARD
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
                submission["user_id"],
                submission["task_id"],
                submission["activity_date"],
            ),
        )

        if updated.rowcount != 1:

            conn.rollback()

            flash(
                "Task reward has already been processed.",
                "warning",
            )

            return redirect(
                url_for("admin_task_submissions")
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
                submission["user_id"],
            ),
        )

        create_transaction(
            conn,
            submission["user_id"],
            "TASK_REWARD",
            reward,
            "Approved daily task reward",
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
                submission["user_id"],
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
        url_for("admin_task_submissions")
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
                url_for("admin_task_submissions")
            )

        if submission["status"] != "Pending":

            flash(
                "This submission has already been reviewed.",
                "warning",
            )

            return redirect(
                url_for("admin_task_submissions")
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
                submission["user_id"],
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
        url_for("admin_task_submissions")
    )


# ============================================================
# PROFILE
# ============================================================

@app.route("/profile")
@login_required
def profile():

    user = current_user()

    conn = get_db()

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

    conn.close()

    referral_link = (
        request.host_url.rstrip("/")
        + "/register?ref="
        + user["referral_code"]
    )

    return render_template(
        "profile.html",
        user=user,
        referral_count=referral_count,
        referral_earnings=referral_earnings,
        referral_link=referral_link,
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
    conn.close()

    return render_template(
        "notifications.html",
        user=user,
        notifications=notifications_list,
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

    conn.close()

    return jsonify(
        {
            "success": True,
            "user": {
                "id": user["id"],
                "phone": user["phone"],
                "saved_balance": user["saved_balance"],
                "withdrawable_balance": user["withdrawable_balance"],
                "total_earned": user["total_earned"],
                "total_withdrawn": user["total_withdrawn"],
                "referral_code": user["referral_code"],
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