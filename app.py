import os
import urllib.parse
from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# ----- DB CONFIG -----
raw_url = os.getenv("DATABASE_URL", "")
# ensure psycopg driver + verify-full pinned (works if already present too)
fixed = raw_url.replace("postgresql://", "postgresql+psycopg://")
if "sslmode=" not in fixed:
    sep = "&" if "?" in fixed else "?"
    fixed += f"{sep}sslmode=verify-full"
if "sslrootcert=" not in fixed:
    sep = "&" if "?" in fixed else "?"
    fixed += f"{sep}sslrootcert=/etc/ssl/certs/ca-certificates.crt"

app.config["SQLALCHEMY_DATABASE_URI"] = fixed
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
db = SQLAlchemy(app)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)

# create tables once on boot if RUN_DB_INIT=1 (default)
if os.getenv("RUN_DB_INIT", "1") == "1":
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning("DB init failed: %r", e)

# ----- ROUTES -----
@app.route("/")
def index():
    # Render HTML page
    items = Item.query.order_by(Item.id.desc()).all()
    return render_template("index.html", items=items)

@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})

# simple API to add a demo item (GET for convenience in demo)
@app.route("/add/<name>")
def add(name):
    it = Item(name=name)
    db.session.add(it)
    db.session.commit()
    return jsonify({"ok": True, "id": it.id, "name": it.name})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))