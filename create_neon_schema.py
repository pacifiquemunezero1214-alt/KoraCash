import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing")

sql = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    phone TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    referral_code TEXT NOT NULL UNIQUE,
    referred_by INTEGER,
    saved_balance INTEGER NOT NULL DEFAULT 0,
    withdrawable_balance INTEGER NOT NULL DEFAULT 0,
    total_earned INTEGER NOT NULL DEFAULT 0,
    total_withdrawn INTEGER NOT NULL DEFAULT 0,
    registration_bonus INTEGER NOT NULL DEFAULT 1500,
    created_at TEXT NOT NULL,
    last_login TEXT,
    withdrawal_locked_until TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    amount INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Completed',
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS withdrawals (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    network TEXT NOT NULL,
    phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS cash_ins (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    payment_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at TEXT NOT NULL,
    confirmed_at TEXT
);

CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY,
    referrer_id INTEGER NOT NULL,
    referred_user_id INTEGER NOT NULL,
    bonus_amount INTEGER NOT NULL DEFAULT 1500,
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at TEXT NOT NULL,
    rewarded_at TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_activities (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    activity_date TEXT NOT NULL,
    video_id INTEGER,
    task_id INTEGER,
    video_completed INTEGER NOT NULL DEFAULT 0,
    task_completed INTEGER NOT NULL DEFAULT 0,
    video_rewarded INTEGER NOT NULL DEFAULT 0,
    task_rewarded INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_submissions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    activity_date TEXT NOT NULL,
    answer TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending',
    submitted_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewer_note TEXT
);
"""

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()

print("NEON SCHEMA: OK")
