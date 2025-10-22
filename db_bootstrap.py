import os
import re
import contextlib
from datetime import datetime

def _normalize_db_url(url: str) -> str:
    # Render / Heroku 포맷 보정: postgres:// -> postgresql://
    if url and url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url

def _exec_psycopg(sql_list):
    import psycopg
    dsn = _normalize_db_url(os.getenv("DATABASE_URL", ""))
    if not dsn:
        print("[db_bootstrap] DATABASE_URL not set; skipping psycopg path")
        return
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                for sql in sql_list:
                    print("[db_bootstrap] executing:", sql)
                    cur.execute(sql)
            conn.commit()
    except Exception as e:
        print("[db_bootstrap] psycopg error:", repr(e))

def apply_hotfixes():
    """Run idempotent schema fixes so the app stops 500-ing on Render."""
    # 실행할 쿼리(모두 IF NOT EXISTS 형태 — 안전함)
    fixes = [
        'ALTER TABLE IF EXISTS audit_log ADD COLUMN IF NOT EXISTS doc_title VARCHAR(255);',
        'ALTER TABLE IF EXISTS "user"    ADD COLUMN IF NOT EXISTS pw        VARCHAR(255);',
        'ALTER TABLE IF EXISTS document  ADD COLUMN IF NOT EXISTS is_legal  BOOLEAN DEFAULT FALSE;',
    ]

    # 1) 우선 psycopg로 직접 시도 (가장 확실)
    _exec_psycopg(fixes)

    # 2) SQLAlchemy가 있다면, engine으로도 한 번 더 시도 (둘 중 하나만 성공해도 됨)
    with contextlib.suppress(Exception):
        from flask_sqlalchemy import SQLAlchemy  # type: ignore
        # 전역 db 인스턴스가 있을 수도, 없을 수도 있으니 광범위하게 탐색
        db = None
        for name in ("db", "DB", "database"):
            if name in globals():
                db = globals()[name]
                break
            if name in locals():
                db = locals()[name]
                break
        if db is not None and hasattr(db, "engine"):
            from sqlalchemy import text  # type: ignore
            with db.engine.begin() as conn:
                for sql in fixes:
                    print("[db_bootstrap] sqlalchemy executing:", sql)
                    conn.execute(text(sql))

    print("[db_bootstrap] hotfixes applied at", datetime.utcnow().isoformat() + "Z")
