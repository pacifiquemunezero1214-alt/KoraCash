from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

# ============================================================
# 1. Replace get_db()
# ============================================================

start = text.find("def get_db():")
end = text.find("\ndef ensure_column(", start)

if start == -1 or end == -1:
    raise RuntimeError("get_db() cyangwa ensure_column() ntibonetse")

new_get_db = r'''class HybridRow(dict):

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

'''

text = text[:start] + new_get_db + text[end:]


# ============================================================
# 2. Replace init_db()
# ============================================================

start = text.find("def init_db():")
end = text.find("\n# ============================================================\n# TIME HELPERS", start)

if start == -1 or end == -1:
    raise RuntimeError("init_db() cyangwa TIME HELPERS ntibibonetse")

old_init = text[start:end]

script_position = old_init.find("    conn.executescript(")

if script_position == -1:
    raise RuntimeError(
        "conn.executescript() ntibonetse muri init_db()"
    )

# Extract SQLite schema section.
sqlite_section = old_init[script_position:]

neon_init = '''def init_db():

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

'''

# Keep original SQLite initialization untouched.
sqlite_section = sqlite_section.rstrip()

new_init = neon_init + sqlite_section + "\n"

text = text[:start] + new_init + text[end:]


# ============================================================
# 3. PostgreSQL-safe IntegrityError handling
# ============================================================

text = text.replace(
    "except sqlite3.IntegrityError as error:",
    "except (sqlite3.IntegrityError, psycopg.errors.UniqueViolation) as error:",
)


# ============================================================
# 4. Fix PostgreSQL INSERT user ID
# ============================================================

old_register = '''            cursor = conn.execute(
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
'''

new_register = '''            if DATABASE_URL:

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
'''

if old_register in text:
    text = text.replace(
        old_register,
        new_register,
        1,
    )
else:
    print(
        "WARNING: Registration block ntabonetse; "
        "ntayihinduwe."
    )


path.write_text(
    text,
    encoding="utf-8",
)

print("NEON COMPATIBILITY: UPDATED")