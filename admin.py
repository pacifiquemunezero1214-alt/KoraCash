import os
import sqlite3

from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)


# ============================================================
# KORACASH ADMIN BLUEPRINT
# ============================================================

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin"
)


# ============================================================
# DATABASE
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE = os.path.join(
    BASE_DIR,
    "koracash.db"
)

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)


def get_db():

    if DATABASE_URL:
        return psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row
        )

    conn = sqlite3.connect(
        DATABASE,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn


def execute_db(
    conn,
    sql,
    params=()
):
    """
    Allows the same admin code to work with
    SQLite and PostgreSQL.

    Existing SQL uses ? placeholders.
    PostgreSQL uses %s.
    """

    if DATABASE_URL:
        sql = sql.replace(
            "?",
            "%s"
        )

    return conn.execute(
        sql,
        params
    )


def now_iso():

    return datetime.now().isoformat(
        timespec="seconds"
    )


# ============================================================
# DATABASE HELPERS
# ============================================================

def table_exists(
    conn,
    table_name
):

    if DATABASE_URL:

        row = execute_db(
            conn,
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema='public'
                AND table_name=?
            ) AS exists
            """,
            (table_name,)
        ).fetchone()

        return bool(
            row["exists"]
        )

    row = execute_db(
        conn,
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name=?
        """,
        (table_name,)
    ).fetchone()

    return row is not None


def column_exists(
    conn,
    table_name,
    column_name
):

    if not table_exists(
        conn,
        table_name
    ):
        return False

    if DATABASE_URL:

        row = execute_db(
            conn,
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema='public'
                AND table_name=?
                AND column_name=?
            ) AS exists
            """,
            (
                table_name,
                column_name
            )
        ).fetchone()

        return bool(
            row["exists"]
        )

    columns = execute_db(
        conn,
        f"""
        PRAGMA table_info({table_name})
        """
    ).fetchall()

    return any(
        row["name"] == column_name
        for row in columns
    )


def safe_value(
    row,
    key,
    default=None
):

    if row is None:
        return default

    try:
        value = row[key]
    except Exception:
        return default

    if value is None:
        return default

    return value


def scalar(
    row,
    default=0
):

    if row is None:
        return default

    if isinstance(row, dict):

        if len(row) == 0:
            return default

        value = next(
            iter(row.values())
        )

    else:

        try:
            value = row[0]
        except Exception:
            return default

    if value is None:
        return default

    return value


def rows_to_dict(rows):

    result = []

    for row in rows:

        if isinstance(row, dict):
            result.append(dict(row))
        else:
            result.append(dict(row))

    return result


# ============================================================
# ADMIN AUTH
# ============================================================

def admin_required():

    return session.get(
        "admin_logged_in",
        False
    )


# ============================================================
# LOGIN
# ============================================================

@admin_bp.route(
    "/login",
    methods=["GET", "POST"]
)
def admin_login():

    if admin_required():

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

    if request.method == "POST":

        phone = (
            request.form.get(
                "phone",
                ""
            )
            .strip()
        )

        password = (
            request.form.get(
                "password",
                ""
            )
            .strip()
        )

        # Admin credentials remain the
        # dedicated admin credentials.

        if (
            phone == "0798386665"
            and password == "121412"
        ):

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

        flash(
            "Invalid admin credentials.",
            "error"
        )

    return render_template(
        "admin_login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@admin_bp.route("/logout")
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    session.pop(
        "admin_phone",
        None
    )

    return redirect(
        url_for("login")
    )


# ============================================================
# DASHBOARD
# ============================================================

@admin_bp.route("/")
def admin_dashboard():

    if not admin_required():

        return redirect(
            url_for("login")
        )

    conn = get_db()

    try:

        # ----------------------------------------------------
        # USERS
        # ----------------------------------------------------

        total_users = 0
        active_users = 0
        inactive_users = 0

        if table_exists(
            conn,
            "users"
        ):

            total_users = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COUNT(*) AS count
                    FROM users
                    """
                ).fetchone()
            )

            if column_exists(
                conn,
                "users",
                "is_active"
            ):

                active_users = scalar(
                    execute_db(
                        conn,
                        """
                        SELECT COUNT(*) AS count
                        FROM users
                        WHERE is_active=1
                        """
                    ).fetchone()
                )

            elif column_exists(
                conn,
                "users",
                "active"
            ):

                active_users = scalar(
                    execute_db(
                        conn,
                        """
                        SELECT COUNT(*) AS count
                        FROM users
                        WHERE active=1
                        """
                    ).fetchone()
                )

            else:

                active_users = total_users

            inactive_users = (
                total_users - active_users
            )

        # ----------------------------------------------------
        # USER BALANCES
        # ----------------------------------------------------

        total_saved = 0
        total_withdrawable = 0
        total_earned = 0
        total_withdrawn = 0

        if table_exists(
            conn,
            "users"
        ):

            total_saved = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COALESCE(
                        SUM(saved_balance),
                        0
                    ) AS total
                    FROM users
                    """
                ).fetchone()
            )

            total_withdrawable = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COALESCE(
                        SUM(withdrawable_balance),
                        0
                    ) AS total
                    FROM users
                    """
                ).fetchone()
            )

            total_earned = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COALESCE(
                        SUM(total_earned),
                        0
                    ) AS total
                    FROM users
                    """
                ).fetchone()
            )

            total_withdrawn = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COALESCE(
                        SUM(total_withdrawn),
                        0
                    ) AS total
                    FROM users
                    """
                ).fetchone()
            )

        # ----------------------------------------------------
        # CASH IN
        # ----------------------------------------------------

        total_cash_in = 0
        confirmed_cash_in = 0
        completed_cash_ins = 0
        pending_cash_in = 0

        if table_exists(
            conn,
            "cash_ins"
        ):

            total_cash_in = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COALESCE(
                        SUM(amount),
                        0
                    ) AS total
                    FROM cash_ins
                    WHERE status='Completed'
                    """
                ).fetchone()
            )

            confirmed_cash_in = total_cash_in

            completed_cash_ins = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COUNT(*) AS count
                    FROM cash_ins
                    WHERE status='Completed'
                    """
                ).fetchone()
            )

            pending_cash_in = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COUNT(*) AS count
                    FROM cash_ins
                    WHERE status='Pending'
                    """
                ).fetchone()
            )

        # ----------------------------------------------------
        # CASH OUT
        # ----------------------------------------------------

        total_cash_out = 0
        completed_cash_out = 0
        completed_cash_outs = 0
        pending_cash_out = 0

        if table_exists(
            conn,
            "withdrawals"
        ):

            total_cash_out = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COALESCE(
                        SUM(amount),
                        0
                    ) AS total
                    FROM withdrawals
                    WHERE status='Completed'
                    """
                ).fetchone()
            )

            completed_cash_out = total_cash_out

            completed_cash_outs = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COUNT(*) AS count
                    FROM withdrawals
                    WHERE status='Completed'
                    """
                ).fetchone()
            )

            pending_cash_out = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COUNT(*) AS count
                    FROM withdrawals
                    WHERE status='Pending'
                    """
                ).fetchone()
            )

        # ----------------------------------------------------
        # REFERRALS
        # ----------------------------------------------------

        referral_rewards = 0
        completed_referrals = 0
        pending_referrals = 0

        if table_exists(
            conn,
            "referrals"
        ):

            if column_exists(
                conn,
                "referrals",
                "bonus_amount"
            ):

                referral_rewards = scalar(
                    execute_db(
                        conn,
                        """
                        SELECT COALESCE(
                            SUM(bonus_amount),
                            0
                        ) AS total
                        FROM referrals
                        WHERE status='Completed'
                        """
                    ).fetchone()
                )

            elif column_exists(
                conn,
                "referrals",
                "reward"
            ):

                referral_rewards = scalar(
                    execute_db(
                        conn,
                        """
                        SELECT COALESCE(
                            SUM(reward),
                            0
                        ) AS total
                        FROM referrals
                        WHERE status='Completed'
                        """
                    ).fetchone()
                )

            elif column_exists(
                conn,
                "referrals",
                "bonus"
            ):

                referral_rewards = scalar(
                    execute_db(
                        conn,
                        """
                        SELECT COALESCE(
                            SUM(bonus),
                            0
                        ) AS total
                        FROM referrals
                        WHERE status='Completed'
                        """
                    ).fetchone()
                )

            completed_referrals = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COUNT(*) AS count
                    FROM referrals
                    WHERE status='Completed'
                    """
                ).fetchone()
            )

            pending_referrals = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COUNT(*) AS count
                    FROM referrals
                    WHERE status='Pending'
                    """
                ).fetchone()
            )

        # ----------------------------------------------------
        # VIDEOS
        # ----------------------------------------------------

        total_videos = 0
        active_videos = 0

        if table_exists(
            conn,
            "videos"
        ):

            total_videos = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COUNT(*) AS count
                    FROM videos
                    """
                ).fetchone()
            )

            active_videos = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COUNT(*) AS count
                    FROM videos
                    WHERE is_active=1
                    """
                ).fetchone()
            )

        # ----------------------------------------------------
        # TASKS
        # ----------------------------------------------------

        total_tasks = 0
        active_tasks = 0

        if table_exists(
            conn,
            "tasks"
        ):

            total_tasks = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COUNT(*) AS count
                    FROM tasks
                    """
                ).fetchone()
            )

            active_tasks = scalar(
                execute_db(
                    conn,
                    """
                    SELECT COUNT(*) AS count
                    FROM tasks
                    WHERE is_active=1
                    """
                ).fetchone()
            )

        # ----------------------------------------------------
        # RECENT USERS
        # ----------------------------------------------------

        recent_users = []

        if table_exists(
            conn,
            "users"
        ):

            recent_users = rows_to_dict(
                execute_db(
                    conn,
                    """
                    SELECT *
                    FROM users
                    ORDER BY id DESC
                    LIMIT 15
                    """
                ).fetchall()
            )

        # ----------------------------------------------------
        # RECENT CASH IN
        # ----------------------------------------------------

        recent_cash_ins = []

        if table_exists(
            conn,
            "cash_ins"
        ):

            recent_cash_ins = rows_to_dict(
                execute_db(
                    conn,
                    """
                    SELECT
                        ci.*,
                        u.phone AS phone
                    FROM cash_ins ci
                    LEFT JOIN users u
                        ON u.id=ci.user_id
                    ORDER BY ci.id DESC
                    LIMIT 15
                    """
                ).fetchall()
            )

        # ----------------------------------------------------
        # RECENT CASH OUT
        # ----------------------------------------------------

        recent_cash_outs = []

        if table_exists(
            conn,
            "withdrawals"
        ):

            recent_cash_outs = rows_to_dict(
                execute_db(
                    conn,
                    """
                    SELECT
                        w.*,
                        u.phone AS phone
                    FROM withdrawals w
                    LEFT JOIN users u
                        ON u.id=w.user_id
                    ORDER BY w.id DESC
                    LIMIT 15
                    """
                ).fetchall()
            )

        # ----------------------------------------------------
        # RECENT TRANSACTIONS
        # ----------------------------------------------------

        recent_transactions = []

        if table_exists(
            conn,
            "transactions"
        ):

            recent_transactions = rows_to_dict(
                execute_db(
                    conn,
                    """
                    SELECT
                        t.*,
                        u.phone AS phone
                    FROM transactions t
                    LEFT JOIN users u
                        ON u.id=t.user_id
                    ORDER BY t.id DESC
                    LIMIT 20
                    """
                ).fetchall()
            )

    finally:

        conn.close()

    return render_template(
        "admin_dashboard.html",

        admin_phone=session.get(
            "admin_phone",
            ""
        ),

        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,

        total_saved=total_saved,

        total_withdrawable=total_withdrawable,
        withdrawable_balance=total_withdrawable,

        total_earned=total_earned,
        total_withdrawn=total_withdrawn,

        total_cash_in=total_cash_in,
        confirmed_cash_in=confirmed_cash_in,
        completed_cash_ins=completed_cash_ins,
        pending_cash_in=pending_cash_in,

        total_cash_out=total_cash_out,
        completed_cash_out=completed_cash_out,
        completed_cash_outs=completed_cash_outs,
        pending_cash_out=pending_cash_out,

        referral_rewards=referral_rewards,
        completed_referrals=completed_referrals,
        pending_referrals=pending_referrals,

        active_videos=active_videos,
        total_videos=total_videos,

        active_tasks=active_tasks,
        total_tasks=total_tasks,

        recent_users=recent_users,
        recent_cash_ins=recent_cash_ins,
        recent_cash_outs=recent_cash_outs,
        recent_transactions=recent_transactions
    )


# ============================================================
# CASH IN - COMPLETE
# ============================================================

@admin_bp.route(
    "/cash-in/<int:cash_in_id>/complete",
    methods=["POST"]
)
def complete_cash_in(cash_in_id):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        cash_in = execute_db(
            conn,
            """
            SELECT *
            FROM cash_ins
            WHERE id=?
            LIMIT 1
            """,
            (cash_in_id,)
        ).fetchone()

        if not cash_in:

            flash(
                "Cash In request not found.",
                "error"
            )

            return redirect(
                url_for(
                    "admin.admin_dashboard"
                )
            )

        if cash_in["status"] != "Pending":

            flash(
                "This Cash In has already been processed.",
                "info"
            )

            return redirect(
                url_for(
                    "admin.admin_dashboard"
                )
            )

    finally:

        conn.close()

    try:

        from app import confirm_cash_in

        result = confirm_cash_in(
            cash_in_id
        )

        # ----------------------------------------------------
        # confirm_cash_in() returns a JSON response.
        # We only need its data here, then redirect the admin
        # back to the dashboard instead of showing raw JSON.
        # ----------------------------------------------------

        if hasattr(result, "get_json"):

            data = result.get_json(
                silent=True
            ) or {}

        elif isinstance(result, dict):

            data = result

        else:

            data = {}

        if data.get("success"):

            flash(
                data.get(
                    "message",
                    "Cash In completed successfully."
                ),
                "success"
            )

        else:

            flash(
                data.get(
                    "message",
                    "Unable to complete Cash In."
                ),
                "error"
            )

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

    except Exception as e:

        print(
            "ADMIN CASH IN COMPLETE ERROR:",
            e
        )

        flash(
            "Unable to complete Cash In.",
            "error"
        )

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

# ============================================================
# CASH OUT - COMPLETE
# ============================================================

@admin_bp.route(
    "/cash-out/<int:withdrawal_id>/complete",
    methods=["POST"]
)
def complete_cash_out(withdrawal_id):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        withdrawal = execute_db(
            conn,
            """
            SELECT *
            FROM withdrawals
            WHERE id=?
            LIMIT 1
            """,
            (withdrawal_id,)
        ).fetchone()

        if not withdrawal:

            flash(
                "Cash Out request not found.",
                "error"
            )

            return redirect(
                url_for(
                    "admin.admin_dashboard"
                )
            )

        if withdrawal["status"] != "Pending":

            flash(
                "This Cash Out has already been processed.",
                "info"
            )

            return redirect(
                url_for(
                    "admin.admin_dashboard"
                )
            )

        completed_at = now_iso()

        execute_db(
            conn,
            """
            UPDATE withdrawals
            SET
                status='Completed',
                completed_at=?
            WHERE id=?
            AND status='Pending'
            """,
            (
                completed_at,
                withdrawal_id
            )
        )

        if table_exists(
            conn,
            "transactions"
        ):

            if column_exists(
                conn,
                "transactions",
                "transaction_type"
            ):

                transaction = execute_db(
                    conn,
                    """
                    SELECT id
                    FROM transactions
                    WHERE user_id=?
                    AND transaction_type='WITHDRAWAL'
                    AND amount=?
                    AND status='Pending'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        withdrawal["user_id"],
                        withdrawal["amount"]
                    )
                ).fetchone()

            else:

                transaction = execute_db(
                    conn,
                    """
                    SELECT id
                    FROM transactions
                    WHERE user_id=?
                    AND type='WITHDRAWAL'
                    AND amount=?
                    AND status='Pending'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        withdrawal["user_id"],
                        withdrawal["amount"]
                    )
                ).fetchone()

            if transaction:

                execute_db(
                    conn,
                    """
                    UPDATE transactions
                    SET status='Completed'
                    WHERE id=?
                    """,
                    (transaction["id"],)
                )

        if table_exists(
            conn,
            "notifications"
        ):

            execute_db(
                conn,
                """
                INSERT INTO notifications
                (
                    user_id,
                    title,
                    message,
                    is_read,
                    created_at
                )
                VALUES
                (?, ?, ?, 0, ?)
                """,
                (
                    withdrawal["user_id"],
                    "Withdrawal Completed",
                    "Your Cash Out request has been completed.",
                    completed_at
                )
            )

        conn.commit()

        flash(
            "Cash Out completed successfully.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "ADMIN CASH OUT COMPLETE ERROR:",
            e
        )

        flash(
            "Unable to complete Cash Out.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin.admin_dashboard"
        )
    )


# ============================================================
# CASH OUT - REJECT + REFUND
# ============================================================

@admin_bp.route(
    "/cash-out/<int:withdrawal_id>/reject",
    methods=["POST"]
)
def reject_cash_out(withdrawal_id):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        withdrawal = execute_db(
            conn,
            """
            SELECT *
            FROM withdrawals
            WHERE id=?
            LIMIT 1
            """,
            (withdrawal_id,)
        ).fetchone()

        if not withdrawal:

            flash(
                "Cash Out request not found.",
                "error"
            )

            return redirect(
                url_for(
                    "admin.admin_dashboard"
                )
            )

        if withdrawal["status"] != "Pending":

            flash(
                "This Cash Out has already been processed.",
                "info"
            )

            return redirect(
                url_for(
                    "admin.admin_dashboard"
                )
            )

        amount = int(
            withdrawal["amount"] or 0
        )

        execute_db(
            conn,
            """
            UPDATE users
            SET
                withdrawable_balance =
                    COALESCE(
                        withdrawable_balance,
                        0
                    ) + ?,

                total_withdrawn =
                    CASE
                        WHEN COALESCE(
                            total_withdrawn,
                            0
                        ) >= ?
                        THEN
                            COALESCE(
                                total_withdrawn,
                                0
                            ) - ?
                        ELSE
                            0
                    END,

                withdrawal_locked_until = NULL

            WHERE id=?
            """,
            (
                amount,
                amount,
                amount,
                withdrawal["user_id"]
            )
        )

        execute_db(
            conn,
            """
            UPDATE withdrawals
            SET status='Rejected'
            WHERE id=?
            AND status='Pending'
            """,
            (withdrawal_id,)
        )

        if table_exists(
            conn,
            "transactions"
        ):

            if column_exists(
                conn,
                "transactions",
                "transaction_type"
            ):

                transaction = execute_db(
                    conn,
                    """
                    SELECT id
                    FROM transactions
                    WHERE user_id=?
                    AND transaction_type='WITHDRAWAL'
                    AND amount=?
                    AND status='Pending'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        withdrawal["user_id"],
                        amount
                    )
                ).fetchone()

            else:

                transaction = execute_db(
                    conn,
                    """
                    SELECT id
                    FROM transactions
                    WHERE user_id=?
                    AND type='WITHDRAWAL'
                    AND amount=?
                    AND status='Pending'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        withdrawal["user_id"],
                        amount
                    )
                ).fetchone()

            if transaction:

                execute_db(
                    conn,
                    """
                    UPDATE transactions
                    SET status='Rejected'
                    WHERE id=?
                    """,
                    (transaction["id"],)
                )

        if table_exists(
            conn,
            "notifications"
        ):

            execute_db(
                conn,
                """
                INSERT INTO notifications
                (
                    user_id,
                    title,
                    message,
                    is_read,
                    created_at
                )
                VALUES
                (?, ?, ?, 0, ?)
                """,
                (
                    withdrawal["user_id"],
                    "Withdrawal Rejected",
                    "Your Cash Out request was rejected and the amount was refunded.",
                    now_iso()
                )
            )

        conn.commit()

        flash(
            "Cash Out rejected and amount refunded.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "ADMIN CASH OUT REJECT ERROR:",
            e
        )

        flash(
            "Unable to reject Cash Out.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin.admin_dashboard"
        )
    )


# ============================================================
# USERS
# ============================================================

@admin_bp.route("/users")
def admin_users():

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        users = rows_to_dict(
            execute_db(
                conn,
                """
                SELECT *
                FROM users
                ORDER BY id DESC
                """
            ).fetchall()
        )

    finally:

        conn.close()

    return render_template(
        "admin_users.html",
        users=users
    )


# ============================================================
# ACTIVATE USER
# ============================================================

@admin_bp.route(
    "/users/<int:user_id>/activate",
    methods=["POST"]
)
def activate_user(user_id):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        if column_exists(
            conn,
            "users",
            "is_active"
        ):

            execute_db(
                conn,
                """
                UPDATE users
                SET is_active=1
                WHERE id=?
                """,
                (user_id,)
            )

        else:

            execute_db(
                conn,
                """
                UPDATE users
                SET active=1
                WHERE id=?
                """,
                (user_id,)
            )

        conn.commit()

        flash(
            "User activated.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "ADMIN ACTIVATE USER ERROR:",
            e
        )

        flash(
            "Unable to activate user.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin.admin_users"
        )
    )


# ============================================================
# DEACTIVATE USER
# ============================================================

@admin_bp.route(
    "/users/<int:user_id>/deactivate",
    methods=["POST"]
)
def deactivate_user(user_id):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        if column_exists(
            conn,
            "users",
            "is_active"
        ):

            execute_db(
                conn,
                """
                UPDATE users
                SET is_active=0
                WHERE id=?
                """,
                (user_id,)
            )

        else:

            execute_db(
                conn,
                """
                UPDATE users
                SET active=0
                WHERE id=?
                """,
                (user_id,)
            )

        conn.commit()

        flash(
            "User deactivated.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "ADMIN DEACTIVATE USER ERROR:",
            e
        )

        flash(
            "Unable to deactivate user.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin.admin_users"
        )
    )


# ============================================================
# TRANSACTIONS
# ============================================================

@admin_bp.route("/transactions")
def admin_transactions():

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        transactions = rows_to_dict(
            execute_db(
                conn,
                """
                SELECT
                    t.*,
                    u.phone AS phone
                FROM transactions t
                LEFT JOIN users u
                    ON u.id=t.user_id
                ORDER BY t.id DESC
                LIMIT 500
                """
            ).fetchall()
        )

    finally:

        conn.close()

    try:

        return render_template(
            "admin_transactions.html",
            transactions=transactions
        )

    except Exception:

        return render_template(
            "admin_dashboard.html",
            admin_phone=session.get(
                "admin_phone",
                ""
            ),
            total_users=0,
            active_users=0,
            inactive_users=0,
            total_saved=0,
            total_withdrawable=0,
            withdrawable_balance=0,
            total_earned=0,
            total_withdrawn=0,
            total_cash_in=0,
            confirmed_cash_in=0,
            completed_cash_ins=0,
            pending_cash_in=0,
            total_cash_out=0,
            completed_cash_out=0,
            completed_cash_outs=0,
            pending_cash_out=0,
            referral_rewards=0,
            completed_referrals=0,
            pending_referrals=0,
            active_videos=0,
            total_videos=0,
            active_tasks=0,
            total_tasks=0,
            recent_users=[],
            recent_cash_ins=[],
            recent_cash_outs=[],
            recent_transactions=transactions
        )


# ============================================================
# TASK LIBRARY
# ============================================================

@admin_bp.route("/tasks")
def admin_tasks():

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        tasks = rows_to_dict(
            execute_db(
                conn,
                """
                SELECT *
                FROM tasks
                ORDER BY id DESC
                """
            ).fetchall()
        )

    finally:

        conn.close()

    return render_template(
        "admin_tasks.html",
        tasks=tasks
    )


# ============================================================
# ACTIVATE TASK
# ============================================================

@admin_bp.route(
    "/tasks/<int:task_id>/activate",
    methods=["POST"]
)
def activate_task(task_id):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        execute_db(
            conn,
            """
            UPDATE tasks
            SET is_active=1
            WHERE id=?
            """,
            (task_id,)
        )

        conn.commit()

        flash(
            "Task activated.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "ADMIN ACTIVATE TASK ERROR:",
            e
        )

        flash(
            "Unable to activate task.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin.admin_tasks"
        )
    )


# ============================================================
# DEACTIVATE TASK
# ============================================================

@admin_bp.route(
    "/tasks/<int:task_id>/deactivate",
    methods=["POST"]
)
def deactivate_task(task_id):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        execute_db(
            conn,
            """
            UPDATE tasks
            SET is_active=0
            WHERE id=?
            """,
            (task_id,)
        )

        conn.commit()

        flash(
            "Task deactivated.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "ADMIN DEACTIVATE TASK ERROR:",
            e
        )

        flash(
            "Unable to deactivate task.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin.admin_tasks"
        )
    )


# ============================================================
# VIDEO LIBRARY
# ============================================================

@admin_bp.route("/videos")
def admin_videos():

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        videos = rows_to_dict(
            execute_db(
                conn,
                """
                SELECT *
                FROM videos
                ORDER BY id DESC
                """
            ).fetchall()
        )

    finally:

        conn.close()

    return render_template(
        "admin_videos.html",
        videos=videos
    )


# ============================================================
# ACTIVATE VIDEO
# ============================================================

@admin_bp.route(
    "/videos/<int:video_id>/activate",
    methods=["POST"]
)
def activate_video(video_id):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        execute_db(
            conn,
            """
            UPDATE videos
            SET is_active=1
            WHERE id=?
            """,
            (video_id,)
        )

        conn.commit()

        flash(
            "Video activated.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "ADMIN ACTIVATE VIDEO ERROR:",
            e
        )

        flash(
            "Unable to activate video.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin.admin_videos"
        )
    )


# ============================================================
# DEACTIVATE VIDEO
# ============================================================

@admin_bp.route(
    "/videos/<int:video_id>/deactivate",
    methods=["POST"]
)
def deactivate_video(video_id):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        execute_db(
            conn,
            """
            UPDATE videos
            SET is_active=0
            WHERE id=?
            """,
            (video_id,)
        )

        conn.commit()

        flash(
            "Video deactivated.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "ADMIN DEACTIVATE VIDEO ERROR:",
            e
        )

        flash(
            "Unable to deactivate video.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin.admin_videos"
        )
    )


# ============================================================
# DAILY ACTIVITIES
# ============================================================

@admin_bp.route("/activities")
def admin_activities():

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        activities = rows_to_dict(
            execute_db(
                conn,
                """
                SELECT
                    da.*,
                    u.phone AS phone,
                    v.title AS video_title,
                    t.title AS task_title
                FROM daily_activities da
                LEFT JOIN users u
                    ON u.id=da.user_id
                LEFT JOIN videos v
                    ON v.id=da.video_id
                LEFT JOIN tasks t
                    ON t.id=da.task_id
                ORDER BY da.id DESC
                LIMIT 500
                """
            ).fetchall()
        )

    finally:

        conn.close()

    return render_template(
        "admin_activities.html",
        activities=activities
    )


# ============================================================
# TASK SUBMISSIONS
# ============================================================

@admin_bp.route(
    "/task-submissions"
)
def admin_task_submissions():

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        if not table_exists(
            conn,
            "task_submissions"
        ):

            submissions = []

        else:

            submissions = rows_to_dict(
                execute_db(
                    conn,
                    """
                    SELECT
                        ts.*,
                        u.phone AS phone,
                        t.title AS task_title
                    FROM task_submissions ts
                    LEFT JOIN users u
                        ON u.id=ts.user_id
                    LEFT JOIN tasks t
                        ON t.id=ts.task_id
                    ORDER BY ts.id DESC
                    LIMIT 500
                    """
                ).fetchall()
            )

    finally:

        conn.close()

    return render_template(
        "admin_task_submissions.html",
        submissions=submissions
    )


# ============================================================
# TASK SUBMISSION DETAIL
# ============================================================

@admin_bp.route(
    "/task-submissions/<int:submission_id>"
)
def task_submission_detail(
    submission_id
):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        submission = execute_db(
            conn,
            """
            SELECT
                ts.*,
                u.phone AS phone,
                t.title AS task_title,
                t.description AS task_description,
                t.option_a,
                t.option_b,
                t.option_c,
                t.option_d,
                t.correct_answer
            FROM task_submissions ts
            LEFT JOIN users u
                ON u.id=ts.user_id
            LEFT JOIN tasks t
                ON t.id=ts.task_id
            WHERE ts.id=?
            LIMIT 1
            """,
            (submission_id,)
        ).fetchone()

    finally:

        conn.close()

    if not submission:

        flash(
            "Task submission not found.",
            "error"
        )

        return redirect(
            url_for(
                "admin.admin_task_submissions"
            )
        )

    return render_template(
        "admin_task_submission_detail.html",
        submission=dict(submission)
    )


# ============================================================
# TASK SUBMISSION APPROVE
# ============================================================

@admin_bp.route(
    "/task-submissions/<int:submission_id>/approve",
    methods=["POST"]
)
def approve_task_submission(
    submission_id
):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        submission = execute_db(
            conn,
            """
            SELECT *
            FROM task_submissions
            WHERE id=?
            LIMIT 1
            """,
            (submission_id,)
        ).fetchone()

        if not submission:

            flash(
                "Submission not found.",
                "error"
            )

            return redirect(
                url_for(
                    "admin.admin_task_submissions"
                )
            )

        if submission["status"] != "Pending":

            flash(
                "This submission has already been reviewed.",
                "info"
            )

            return redirect(
                url_for(
                    "admin.admin_task_submissions"
                )
            )

        # ----------------------------------------------------
        # PLAN-BASED TASK REWARD
        # ----------------------------------------------------
        # Plan 3,000 = 300 Frw
        # Plan 6,000 = 600 Frw
        #
        # We intentionally do NOT use tasks.reward here because
        # old database task records may still contain 1,000 Frw.
        # ----------------------------------------------------

        user = execute_db(
            conn,
            """
            SELECT save_plan
            FROM users
            WHERE id=?
            LIMIT 1
            """,
            (submission["user_id"],)
        ).fetchone()

        plan = 0

        if user and user["save_plan"]:

            try:

                plan = int(
                    user["save_plan"]
                )

            except (
                TypeError,
                ValueError
            ):

                plan = 0

        if plan == 6000:

            reward = 600

        elif plan == 3000:

            reward = 300

        else:

            flash(
                "User does not have a valid savings plan.",
                "error"
            )

            return redirect(
                url_for(
                    "admin.admin_task_submissions"
                )
            )

        # ----------------------------------------------------
        # APPROVE SUBMISSION
        # ----------------------------------------------------

        execute_db(
            conn,
            """
            UPDATE task_submissions
            SET
                status='Approved',
                reviewer_note='Approved by admin'
            WHERE id=?
            """,
            (submission_id,)
        )

        # ----------------------------------------------------
        # ADD REWARD TO USER
        # ----------------------------------------------------

        execute_db(
            conn,
            """
            UPDATE users
            SET
                withdrawable_balance =
                    COALESCE(
                        withdrawable_balance,
                        0
                    ) + ?,

                total_earned =
                    COALESCE(
                        total_earned,
                        0
                    ) + ?

            WHERE id=?
            """,
            (
                reward,
                reward,
                submission["user_id"]
            )
        )

        # ----------------------------------------------------
        # CREATE TASK REWARD TRANSACTION
        # ----------------------------------------------------

        if table_exists(
            conn,
            "transactions"
        ):

            if column_exists(
                conn,
                "transactions",
                "transaction_type"
            ):

                existing_transaction = execute_db(
                    conn,
                    """
                    SELECT id
                    FROM transactions
                    WHERE user_id=?
                    AND transaction_type='TASK_REWARD'
                    AND description LIKE ?
                    LIMIT 1
                    """,
                    (
                        submission["user_id"],
                        f"%submission {submission_id}%"
                    )
                ).fetchone()

            else:

                existing_transaction = execute_db(
                    conn,
                    """
                    SELECT id
                    FROM transactions
                    WHERE user_id=?
                    AND type='TASK_REWARD'
                    AND description LIKE ?
                    LIMIT 1
                    """,
                    (
                        submission["user_id"],
                        f"%submission {submission_id}%"
                    )
                ).fetchone()

            if not existing_transaction:

                if column_exists(
                    conn,
                    "transactions",
                    "transaction_type"
                ):

                    execute_db(
                        conn,
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
                        VALUES
                        (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            submission["user_id"],
                            "TASK_REWARD",
                            reward,
                            "Completed",
                            (
                                f"Task reward - "
                                f"submission {submission_id} "
                                f"- Plan {plan:,}"
                            ),
                            now_iso()
                        )
                    )

                else:

                    execute_db(
                        conn,
                        """
                        INSERT INTO transactions
                        (
                            user_id,
                            type,
                            amount,
                            status,
                            description,
                            created_at
                        )
                        VALUES
                        (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            submission["user_id"],
                            "TASK_REWARD",
                            reward,
                            "Completed",
                            (
                                f"Task reward - "
                                f"submission {submission_id} "
                                f"- Plan {plan:,}"
                            ),
                            now_iso()
                        )
                    )

        # ----------------------------------------------------
        # NOTIFICATION
        # ----------------------------------------------------

        if table_exists(
            conn,
            "notifications"
        ):

            execute_db(
                conn,
                """
                INSERT INTO notifications
                (
                    user_id,
                    title,
                    message,
                    is_read,
                    created_at
                )
                VALUES
                (?, ?, ?, 0, ?)
                """,
                (
                    submission["user_id"],
                    "Task Approved",
                    (
                        f"Your task was approved. "
                        f"You earned {reward:,} Frw "
                        f"from Plan {plan:,}."
                    ),
                    now_iso()
                )
            )

        conn.commit()

        flash(
            "Task submission approved.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "ADMIN APPROVE TASK ERROR:",
            e
        )

        flash(
            "Unable to approve submission.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin.admin_task_submissions"
        )
    )


# ============================================================
# TASK SUBMISSION REJECT
# ============================================================

@admin_bp.route(
    "/task-submissions/<int:submission_id>/reject",
    methods=["POST"]
)
def reject_task_submission(
    submission_id
):

    if not admin_required():
        return redirect(url_for("login"))

    conn = get_db()

    try:

        submission = execute_db(
            conn,
            """
            SELECT *
            FROM task_submissions
            WHERE id=?
            LIMIT 1
            """,
            (submission_id,)
        ).fetchone()

        if not submission:

            flash(
                "Submission not found.",
                "error"
            )

            return redirect(
                url_for(
                    "admin.admin_task_submissions"
                )
            )

        if submission["status"] != "Pending":

            flash(
                "This submission has already been reviewed.",
                "info"
            )

            return redirect(
                url_for(
                    "admin.admin_task_submissions"
                )
            )

        execute_db(
            conn,
            """
            UPDATE task_submissions
            SET
                status='Rejected',
                reviewer_note='Rejected by admin'
            WHERE id=?
            """,
            (submission_id,)
        )

        if table_exists(
            conn,
            "notifications"
        ):

            execute_db(
                conn,
                """
                INSERT INTO notifications
                (
                    user_id,
                    title,
                    message,
                    is_read,
                    created_at
                )
                VALUES
                (?, ?, ?, 0, ?)
                """,
                (
                    submission["user_id"],
                    "Task Rejected",
                    "Your task submission was rejected.",
                    now_iso()
                )
            )

        conn.commit()

        flash(
            "Task submission rejected.",
            "success"
        )

    except Exception as e:

        conn.rollback()

        print(
            "ADMIN REJECT TASK ERROR:",
            e
        )

        flash(
            "Unable to reject submission.",
            "error"
        )

    finally:

        conn.close()

    return redirect(
        url_for(
            "admin.admin_task_submissions"
        )
    )


# ============================================================
# ADMIN SEARCH
# ============================================================

@admin_bp.route("/search")
def admin_search():

    if not admin_required():
        return redirect(url_for("login"))

    query = (
        request.args.get(
            "q",
            ""
        )
        .strip()
    )

    conn = get_db()

    try:

        users = []

        if query and table_exists(
            conn,
            "users"
        ):

            users = rows_to_dict(
                execute_db(
                    conn,
                    """
                    SELECT *
                    FROM users
                    WHERE phone LIKE ?
                    ORDER BY id DESC
                    LIMIT 50
                    """,
                    (
                        f"%{query}%"
                    ,)
                ).fetchall()
            )

    finally:

        conn.close()

    try:

        return render_template(
            "admin_search.html",
            query=query,
            users=users
        )

    except Exception:

        return render_template(
            "admin_users.html",
            users=users
        )


# ============================================================
# REGISTER BLUEPRINT
# ============================================================

def register_admin(app):

    app.register_blueprint(
        admin_bp
    )