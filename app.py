
import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime

app = Flask(__name__)

# ---- DATABASE URL FIX (psycopg3 + ssl) ----
uri = os.environ.get("DATABASE_URL", "").strip()
if uri.startswith("postgresql://"):
    uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
if "sslmode=" not in uri and uri:
    uri += ("&" if "?" in uri else "?") + "sslmode=require"

app.config["SQLALCHEMY_DATABASE_URI"] = uri or "sqlite:///local.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 5,
    "max_overflow": 10,
}

db = SQLAlchemy(app)

class Page(db.Model):
    __tablename__ = "pages"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    content = db.Column(db.Text)
    parent_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PageLog(db.Model):
    __tablename__ = "page_logs"
    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer)
    author = db.Column(db.String)
    action = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()
    try:
        db.session.execute(text("select 1"))
        app.logger.info("[DB] Connected OK")
    except Exception as e:
        app.logger.error(f"[DB] Connection FAILED: {e}")
        # re-raise so Render shows deploy failure loudly
        raise

@app.route("/")
def index():
    pages = Page.query.order_by(Page.id.desc()).all()
    return render_template("index.html", pages=pages)

@app.route("/pages/new", methods=["GET","POST"])
def new_page():
    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form["content"]
        p = Page(title=title or "(제목없음)", content=content)
        db.session.add(p)
        db.session.commit()
        db.session.add(PageLog(page_id=p.id, author="system", action="create"))
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("new_page.html")

@app.route("/p/<int:pid>")
def view_page(pid):
    page = Page.query.get_or_404(pid)
    logs = PageLog.query.filter_by(page_id=pid).order_by(PageLog.id.desc()).all()
    return render_template("view_page.html", page=page, logs=logs)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
