
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError
from datetime import datetime

# --- Config helpers ---------------------------------------------------------
def get_db_uri() -> str:
    # Prefer a single DATABASE_URL/SQLALCHEMY_DATABASE_URI env var
    uri = os.getenv("SQLALCHEMY_DATABASE_URI") or os.getenv("DATABASE_URL", "")
    if not uri:
        # Local fallback (sqlite) so app can boot without a DB
        return "sqlite:///local.db"
    # Render + SQLAlchemy sometimes provide "postgres://" which SQLAlchemy 2+ rewrites
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql+psycopg://", 1)
    # Ensure sslmode=require is present for Supabase
    if "sslmode=" not in uri and "localhost" not in uri and "127.0.0.1" not in uri:
        sep = "&" if "?" in uri else "?"
        uri = f"{uri}{sep}sslmode=require"
    return uri

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = get_db_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    return app

app = create_app()
db = SQLAlchemy(app)

# --- Models -----------------------------------------------------------------
class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, unique=True)
    content = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Page {self.title!r}>"

# Initialize tables on boot, but don't crash if DB unreachable
with app.app_context():
    try:
        db.create_all()
    except OperationalError:
        # App can still start and show a friendly message
        pass

# --- Routes -----------------------------------------------------------------
@app.route("/")
def index():
    try:
        pages = Page.query.order_by(Page.updated_at.desc()).all()
    except OperationalError:
        pages = []
        flash("데이터베이스 연결을 기다리는 중입니다. 잠시 후 새로고침 해주세요.", "warning")
    return render_template("index.html", pages=pages)

@app.route("/new", methods=["GET", "POST"])
def new_page():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        if not title:
            flash("제목을 입력하세요.", "danger")
            return redirect(url_for("new_page"))
        try:
            page = Page(title=title, content=content)
            db.session.add(page)
            db.session.commit()
            flash("페이지가 생성되었습니다.", "success")
            return redirect(url_for("index"))
        except OperationalError:
            flash("DB 연결에 문제가 있습니다. 잠시 후 다시 시도하세요.", "danger")
            return redirect(url_for("index"))
    return render_template("edit.html", page=None)

@app.route("/edit/<int:page_id>", methods=["GET","POST"])
def edit_page(page_id):
    try:
        page = Page.query.get_or_404(page_id)
    except OperationalError:
        flash("DB 연결에 문제가 있습니다.", "danger")
        return redirect(url_for("index"))
    if request.method == "POST":
        page.title = request.form.get("title","").strip() or page.title
        page.content = request.form.get("content","")
        try:
            db.session.commit()
            flash("저장되었습니다.", "success")
            return redirect(url_for("index"))
        except OperationalError:
            flash("DB 연결에 문제가 있습니다. 잠시 후 다시 시도하세요.", "danger")
            return redirect(url_for("index"))
    return render_template("edit.html", page=page)

@app.route("/view/<int:page_id>")
def view_page(page_id):
    try:
        page = Page.query.get_or_404(page_id)
    except OperationalError:
        flash("DB 연결에 문제가 있습니다.", "danger")
        return redirect(url_for("index"))
    return render_template("view.html", page=page)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
