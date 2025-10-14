
"""
Autofix Bootstrap for Render (drop-in)
-------------------------------------
Usage in your app.py (AFTER `db = SQLAlchemy(app)` and BEFORE any queries/seeding):

    from autofix_bootstrap import init_autofix
    init_autofix(app, db)

This will:
- Create missing tables (user, document).
- Add missing columns used by the app:
  - user.password (TEXT / VARCHAR)
  - document.content (TEXT)
  - document.created_by (VARCHAR)
- Register stub endpoints to prevent BuildError:
  - 'withdraw' (POST) -> redirect to index
  - 'create' (GET) -> redirect to index (adjust later if you have a create page)
  - 'view_document' (GET) -> redirect to 'edit_document' if present; else index
It does NOT change templates or visual design.
"""
from __future__ import annotations

from typing import Optional, Iterable
import os
from datetime import datetime
from flask import Blueprint, redirect, url_for, current_app, request
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError, OperationalError
from werkzeug.routing import BuildError

def _is_sqlite(uri: str) -> bool:
    return uri.startswith("sqlite:")

def _exec(conn, sql: str):
    try:
        conn.execute(text(sql))
    except Exception as e:
        current_app.logger.warning("Autofix SQL skipped/failed: %s (%s)", sql, e)

def _table_exists(engine: Engine, table: str) -> bool:
    try:
        with engine.connect() as conn:
            if engine.url.get_backend_name() == "sqlite":
                res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table})
                return res.first() is not None
            else:
                res = conn.execute(text("""
                    SELECT to_regclass(:t) IS NOT NULL
                """), {"t": table})
                row = res.first()
                return bool(row[0]) if row else False
    except Exception:
        return False

def _column_names(engine: Engine, table: str) -> set[str]:
    cols = set()
    try:
        with engine.connect() as conn:
            if engine.url.get_backend_name() == "sqlite":
                res = conn.execute(text(f"PRAGMA table_info('{table}')"))
                for cid, name, ctype, notnull, dflt, pk in res.fetchall():
                    cols.add(name)
            else:
                res = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = :t
                """), {"t": table})
                cols = {r[0] for r in res}
    except Exception:
        pass
    return cols

def _ensure_tables_and_columns(app, db):
    engine: Engine = db.engine

    # 1) Create base tables if missing using SQLAlchemy models
    #    (create_all is idempotent)
    try:
        db.create_all()
    except Exception as e:
        app.logger.warning("Autofix: db.create_all() warning: %s", e)

    # 2) Ensure required columns exist, add if missing (safe for both PG / SQLite)
    with engine.begin() as conn:
        # user.password
        if _table_exists(engine, 'user'):
            ucols = _column_names(engine, 'user')
            if 'password' not in ucols:
                if engine.url.get_backend_name() == "sqlite":
                    _exec(conn, "ALTER TABLE \"user\" ADD COLUMN password TEXT")
                else:
                    _exec(conn, "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS password VARCHAR(255)")
        # document.content, document.created_by
        if _table_exists(engine, 'document'):
            dcols = _column_names(engine, 'document')
            if 'content' not in dcols:
                if engine.url.get_backend_name() == "sqlite":
                    _exec(conn, "ALTER TABLE document ADD COLUMN content TEXT")
                else:
                    _exec(conn, "ALTER TABLE document ADD COLUMN IF NOT EXISTS content TEXT")
            if 'created_by' not in dcols:
                if engine.url.get_backend_name() == "sqlite":
                    _exec(conn, "ALTER TABLE document ADD COLUMN created_by VARCHAR(255)")
                else:
                    _exec(conn, "ALTER TABLE document ADD COLUMN IF NOT EXISTS created_by VARCHAR(255)")

def _register_stub_endpoints(app):
    bp = Blueprint("autofix_stubs", __name__)

    @bp.route("/withdraw", methods=["POST"])
    def withdraw():
        try:
            return redirect(url_for("index"))
        except BuildError:
            return redirect("/")

    @bp.route("/create", methods=["GET"])
    def create():
        # If you have a real create endpoint, change the redirect target accordingly.
        try:
            return redirect(url_for("index"))
        except BuildError:
            return redirect("/")

    @bp.route("/documents/<int:doc_id>", methods=["GET"])
    def view_document(doc_id: int):
        # Prefer edit_document if exists, otherwise index
        try:
            return redirect(url_for("edit_document", doc_id=doc_id))
        except BuildError:
            try:
                return redirect(url_for("index"))
            except BuildError:
                return redirect("/")

    app.register_blueprint(bp)

def init_autofix(app, db):
    """
    Call once on startup AFTER db init, BEFORE any queries/seeding.
    """
    _register_stub_endpoints(app)
    _ensure_tables_and_columns(app, db)
    app.logger.info("Autofix bootstrap completed.")
