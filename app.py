
import os, time
from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# ----- DB CONFIG -----
db_uri = os.getenv("DATABASE_URL", "")
if db_uri.startswith("postgresql://"):
    db_uri = db_uri.replace("postgresql://", "postgresql+psycopg://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {"sslmode": "require"},
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 5,
    "max_overflow": 2,
    "pool_timeout": 30,
}

db = SQLAlchemy(app)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)

def init_db_with_retry(max_attempts=5, delay=1.5):
    attempt = 1
    while True:
        try:
            with app.app_context():
                db.create_all()
            app.logger.info("DB init OK")
            return
        except Exception as e:
            app.logger.warning(f"DB init failed (attempt {attempt}/{max_attempts}): {e}")
            if attempt >= max_attempts:
                app.config["DB_INIT_ERROR"] = str(e)
                return
            time.sleep(delay)
            attempt += 1
            delay *= 1.7

if os.getenv("RUN_DB_INIT", "1") == "1":
    init_db_with_retry()

@app.route("/")
def index():
    try:
        items = Item.query.order_by(Item.id.desc()).all()
        return render_template("index.html", items=items, db_error=None)
    except Exception as e:
        return render_template("index.html", items=[], db_error=str(e))

@app.route("/add/<name>")
def add(name):
    try:
        it = Item(name=name)
        db.session.add(it)
        db.session.commit()
        return jsonify({"ok": True, "id": it.id, "name": it.name})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/healthz")
def healthz():
    return jsonify(status="ok")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
