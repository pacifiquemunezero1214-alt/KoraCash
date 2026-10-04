import sqlite3
from datetime import datetime, timezone

DB_NAME = "koracash.db"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def column_exists(conn, table_name, column_name):
    columns = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(column[1] == column_name for column in columns)


def add_column(conn, table_name, column_name, column_definition):
    if not column_exists(conn, table_name, column_name):
        conn.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {column_definition}"
        )
        print(f"Added: {table_name}.{column_name}")
    else:
        print(f"Exists: {table_name}.{column_name}")


def main():
    conn = sqlite3.connect(DB_NAME)

    try:
        print("\n=== VIDEO LIBRARY MIGRATION ===")

        add_column(
            conn,
            "videos",
            "duration_seconds",
            "INTEGER DEFAULT 0"
        )

        add_column(
            conn,
            "videos",
            "category",
            "TEXT DEFAULT 'General'"
        )

        add_column(
            conn,
            "videos",
            "source",
            "TEXT DEFAULT 'Unknown'"
        )

        add_column(
            conn,
            "videos",
            "license",
            "TEXT DEFAULT 'Unknown'"
        )

        print("\n=== TASK LIBRARY MIGRATION ===")

        add_column(
            conn,
            "tasks",
            "category",
            "TEXT DEFAULT 'General'"
        )

        add_column(
            conn,
            "tasks",
            "option_a",
            "TEXT"
        )

        add_column(
            conn,
            "tasks",
            "option_b",
            "TEXT"
        )

        add_column(
            conn,
            "tasks",
            "option_c",
            "TEXT"
        )

        add_column(
            conn,
            "tasks",
            "option_d",
            "TEXT"
        )

        add_column(
            conn,
            "tasks",
            "correct_answer",
            "TEXT"
        )

        print("\n=== TASK SUBMISSIONS TABLE ===")

        conn.execute("""
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

                UNIQUE(user_id, task_id, activity_date),

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (task_id)
                    REFERENCES tasks(id)
                    ON DELETE CASCADE
            )
        """)

        print("task_submissions table ready.")

        print("\n=== ACTIVITY INDEXES ===")

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_daily_activities_user_date
            ON daily_activities(user_id, activity_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_task_submissions_user_date
            ON task_submissions(user_id, activity_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_videos_active
            ON videos(is_active)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_tasks_active
            ON tasks(is_active)
        """)

        conn.commit()

        print("\n=== MIGRATION COMPLETED SUCCESSFULLY ===")

    except Exception as e:
        conn.rollback()
        print("\nERROR:")
        print(e)

    finally:
        conn.close()


if __name__ == "__main__":
    main()