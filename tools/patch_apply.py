#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Idempotent minimal patcher for app.py
- Adds _ensure_audit_table and _log_action utilities (if missing)
- Rewrites /logs route to a safe direct-SQL variant (if present)
It avoids touching any CSS/templates beyond adding templates/logs.html that ships with this patch.
"""
import re, sys, pathlib

APP = pathlib.Path("app.py")
if not APP.exists():
    print("[patch] app.py not found in current dir. Run this from your project root.", file=sys.stderr)
    sys.exit(1)

src = APP.read_text(encoding="utf-8")

UTIL_BLOCK = """
# ---- AUDIT LOG: 최소 침습형 유틸 ----
from sqlalchemy import text

def _ensure_audit_table(db):
    ddl = \"\"\"
    CREATE TABLE IF NOT EXISTS audit_log (
      id BIGSERIAL PRIMARY KEY,
      user_email TEXT NOT NULL,
      action TEXT NOT NULL,
      doc_title TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    ALTER TABLE audit_log
      ADD COLUMN IF NOT EXISTS user_email TEXT NOT NULL;
    ALTER TABLE audit_log
      ADD COLUMN IF NOT EXISTS action TEXT NOT NULL;
    ALTER TABLE audit_log
      ADD COLUMN IF NOT EXISTS doc_title TEXT;
    ALTER TABLE audit_log
      ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
    \"\"\"
    with db.engine.begin() as conn:
        for stmt in ddl.strip().split(\";\"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))

def _log_action(db, user_email: str, action: str, doc_title: str|None):
    _ensure_audit_table(db)
    with db.engine.begin() as conn:
        conn.execute(
            text(\"INSERT INTO audit_log (user_email, action, doc_title) VALUES (:u,:a,:t)\"),
            {\"u\": user_email or \"(anonymous)\", \"a\": action, \"t\": doc_title}
        )
# ---- /AUDIT LOG ----
""".strip("\n")

# 1) ensure utils present (insert after first Flask import block)
if "_log_action(" not in src:
    m = re.search(r"(from\\s+flask[^\\n]+\\n(?:.+\\n)*?)\\n", src, flags=re.M)
    insert_at = m.end(0) if m else 0
    src = src[:insert_at] + "\\n" + UTIL_BLOCK + "\\n" + src[insert_at:]
    changed_utils = True
else:
    changed_utils = False

# 2) replace /logs route to direct-SQL
pattern = re.compile(r"@app\\.route\\([\\\"']\\/logs[\\\"']\\).*?def\\s+([a-zA-Z_][\\w]*)\\s*\\(\\)\\s*:\\s*(?:.|\\n)*?(?=^\\S|\\Z)", re.M)
m = pattern.search(src)
changed_logs = False
if m:
    replacement = """
@app.route("/logs")
@login_required
def view_logs():
    _ensure_audit_table(db)
    rows = []
    from sqlalchemy import text as _text  # local import to avoid global pollution
    with db.engine.begin() as conn:
        res = conn.execute(_text(\"\"\"
            SELECT id, user_email, action, doc_title, created_at
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT 500
        \"\"\"))
        rows = [dict(r._mapping) for r in res]
    return render_template("logs.html", logs=rows)
"""
    src = src[:m.start()] + replacement + src[m.end():]
    changed_logs = True

if not changed_utils and not changed_logs:
    print("[patch] Nothing to change; already patched or code layout differs. No errors.")
else:
    APP.write_text(src, encoding="utf-8")
    print(f"[patch] Patched app.py. utils_added={changed_utils} logs_route_updated={changed_logs}")
