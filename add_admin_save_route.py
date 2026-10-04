from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

marker = "# ============================================================\n# ADMIN TASK SUBMISSIONS\n# ============================================================"

route = '''# ============================================================
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


'''

if marker not in text:
    raise SystemExit("MARKER NOT FOUND - NO CHANGES MADE")

if 'def admin_save_requests():' in text:
    raise SystemExit("ROUTE ALREADY EXISTS - NO CHANGES MADE")

text = text.replace(marker, route + marker, 1)
path.write_text(text, encoding="utf-8")

print("ADMIN SAVE REQUESTS ROUTE ADDED")
