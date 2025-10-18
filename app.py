import os
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy

def _normalize_db_url(raw: str) -> str:
    """
    - Force driver to psycopg (SQLAlchemy 2.x / psycopg3)
    - Ensure sslmode=verify-full, sslrootcert path
    """
    if not raw:
        return raw

    # If scheme is postgresql:// or postgresql+psycopg:// etc, normalize to +psycopg
    if raw.startswith("postgresql://"):
        raw = "postgresql+psycopg://" + raw[len("postgresql://"):]

    # Parse URL
    p = urlparse(raw)
    # Parse and update query params
    q = dict(parse_qsl(p.query, keep_blank_values=True))

    # TLS: enforce verify-full + root cert bundle path
    q.setdefault("sslmode", "verify-full")
    q.setdefault("sslrootcert", "/etc/ssl/certs/ca-certificates.crt")

    new_query = urlencode(q)
    new_url = urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))
    return new_url

app = Flask(__name__)

# SQLAlchemy config
db_url = _normalize_db_url(os.environ.get("DATABASE_URL", ""))
if not db_url:
    # Fallback to local sqlite to allow booting without DB for e.g. health checks
    db_url = "sqlite:///local.db"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Extra engine options: pre-ping and duplicate TLS guarantees
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "connect_args": {
        "sslmode": "verify-full",
        "sslrootcert": "/etc/ssl/certs/ca-certificates.crt",
    } if db_url.startswith("postgresql+psycopg://") else {}
}

db = SQLAlchemy(app)

# Example model
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)

@app.route("/")
def index():
    return jsonify(status="ok", db_uri=app.config["SQLALCHEMY_DATABASE_URI"].split("?")[0])

@app.route("/items")
def items():
    data = [{"id": it.id, "name": it.name} for it in Item.query.order_by(Item.id).all()]
    return jsonify(items=data)

def init_db():
    # Ensure create_all runs under an app context
    with app.app_context():
        db.create_all()

# Optionally run DB init on startup once. You can disable by setting RUN_DB_INIT=0
if os.environ.get("RUN_DB_INIT", "1") == "1":
    try:
        init_db()
    except Exception as e:
        # Avoid crash loop: log to stdout and keep booting so Render health checks can hit '/'
        print("DB init failed:", repr(e))
