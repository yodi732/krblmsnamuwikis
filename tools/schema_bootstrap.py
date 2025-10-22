import sqlalchemy as sa
from sqlalchemy import text

def _ensure_columns(engine):
    insp = sa.inspect(engine)

    # document.is_legal 추가
    try:
        doc_cols = {c["name"] for c in insp.get_columns("document")}
        if "is_legal" not in doc_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE document ADD COLUMN is_legal BOOLEAN DEFAULT FALSE"))
    except Exception:
        pass

    # audit_log.user_email 추가
    try:
        log_cols = {c["name"] for c in insp.get_columns("audit_log")}
        if "user_email" not in log_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE audit_log ADD COLUMN user_email TEXT"))
    except Exception:
        pass

def init_schema_bootstrap(app, db):
    @app.before_first_request
    def _bootstrap():
        try:
            db.create_all()
        except Exception:
            pass
        try:
            _ensure_columns(db.engine)
        except Exception:
            pass
