\
import os
import time
from urllib.parse import urlparse

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

raw_uri = os.environ.get("DATABASE_URL", "").strip()

def _normalize_db_uri(u: str) -> str:
    if not u:
        return ""
    if u.startswith("postgresql://"):
        u = "postgresql+psycopg://" + u[len("postgresql://"):]
    if "postgresql" in u and "sslmode=" not in u:
        sep = "&" if "?" in u else "?"
        u = f"{u}{sep}sslmode=require"
    return u

db_uri = _normalize_db_uri(raw_uri) or "sqlite:///local.db"

app.config.update(
    SQLALCHEMY_DATABASE_URI=db_uri,
    SQLALCHEMY_ENGINE_OPTIONS={
        "pool_pre_ping": True,
        "pool_recycle": 300,
    },
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)

db = SQLAlchemy(app)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

def init_db_with_retry(max_attempts: int = 5, delay: float = 1.5):
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            with app.app_context():
                db.create_all()
            app.logger.info("DB init OK")
            return
        except Exception as e:
            last_exc = e
            app.logger.warning("DB init failed (attempt %s/%s): %s", attempt, max_attempts, e)
            time.sleep(delay)
    if last_exc:
        app.logger.error("DB init give up: %s", last_exc)

try:
    init_db_with_retry()
except Exception as e:
    app.logger.error("DB init fatal: %s", e)

@app.route("/healthz")
def healthz():
    try:
        if "sqlite" not in app.config["SQLALCHEMY_DATABASE_URI"]:
            db.session.execute(db.text("SELECT 1"))
        return "ok"
    except Exception as e:
        return ("db-error: " + str(e)), 500

@app.route("/add/<name>")
def add(name):
    it = Item(name=name)
    db.session.add(it)
    db.session.commit()
    return f"added #{it.id}: {it.name}"

@app.route("/")
def index():
    err = None
    items = []
    try:
        items = Item.query.order_by(Item.id.desc()).all()
    except Exception as e:
        err = str(e)
    safe_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if "@" in safe_uri:
        try:
            p = urlparse(safe_uri)
            netloc = p.hostname or ""
            if p.port:
                netloc += f":{p.port}"
            safe_uri = f"{p.scheme}://***:***@{netloc}{p.path or ''}{('?'+p.query) if p.query else ''}"
        except Exception:
            safe_uri = "postgresql+psycopg://***:***@***"
    return render_template("index.html", items=items, db_uri=safe_uri, error=err)

@app.route("/favicon.ico")
def favicon():
    from flask import send_from_directory
    return send_from_directory("static", "favicon.ico", mimetype="image/x-icon")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
