import os
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

def normalize_database_url(raw):
    if not raw:
        return None
    url = raw.replace("postgres://", "postgresql://")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    p = urlparse(url)
    # Use pgBouncer port when talking to Supabase unless already 6543
    host = p.hostname or ""
    port = p.port
    if host.endswith("supabase.co") and (port in (None, 5432)):
        netloc = f"{p.username}:{p.password}@{host}:6543"
        p = p._replace(netloc=netloc)
    qs = dict(parse_qsl(p.query, keep_blank_values=True))
    qs.setdefault("sslmode", "require")
    qs.setdefault("connect_timeout", "10")
    new_q = urlencode(qs)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_q, p.fragment))

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-key")
    raw = os.environ.get("DATABASE_URL")
    norm = normalize_database_url(raw)
    app.config["SQLALCHEMY_DATABASE_URI"] = norm or "sqlite:///local.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    class Page(db.Model):
        __tablename__ = "pages"
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(200), unique=True, nullable=False)
        body = db.Column(db.Text, default="")
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    class ChangeLog(db.Model):
        __tablename__ = "change_logs"
        id = db.Column(db.Integer, primary_key=True)
        page_id = db.Column(db.Integer, db.ForeignKey("pages.id"), nullable=False)
        actor = db.Column(db.String(120))
        action = db.Column(db.String(40))
        detail = db.Column(db.Text)
        at = db.Column(db.DateTime, default=datetime.utcnow)

    app.Page = Page
    app.ChangeLog = ChangeLog

    @app.before_first_request
    def _init_db():
        try:
            db.create_all()
        except Exception as e:
            app.logger.error("DB init failed: %s", e)

    @app.route("/")
    def home():
        pages = Page.query.order_by(Page.updated_at.desc()).all()
        return render_template("index.html", pages=pages)

    @app.route("/new", methods=["GET", "POST"])
    def new_page():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            body = request.form.get("body", "")
            if not title:
                flash("제목이 필요합니다.", "error")
                return redirect(url_for("new_page"))
            if Page.query.filter_by(title=title).first():
                flash("같은 제목의 문서가 이미 있습니다.", "error")
                return redirect(url_for("new_page"))
            p = Page(title=title, body=body)
            db.session.add(p)
            db.session.commit()
            db.session.add(ChangeLog(page_id=p.id, actor="system", action="create", detail=f"'{title}' 생성"))
            db.session.commit()
            return redirect(url_for("view_page", page_id=p.id))
        return render_template("edit.html", page=None)

    @app.route("/page/<int:page_id>")
    def view_page(page_id: int):
        p = Page.query.get_or_404(page_id)
        logs = ChangeLog.query.filter_by(page_id=page_id).order_by(ChangeLog.at.desc()).limit(20).all()
        return render_template("view.html", page=p, logs=logs)

    @app.route("/page/<int:page_id>/edit", methods=["GET", "POST"])
    def edit_page(page_id: int):
        p = Page.query.get_or_404(page_id)
        if request.method == "POST":
            p.title = request.form.get("title", p.title)
            p.body = request.form.get("body", p.body)
            db.session.commit()
            db.session.add(ChangeLog(page_id=p.id, actor="system", action="update", detail="본문/제목 수정"))
            db.session.commit()
            return redirect(url_for("view_page", page_id=p.id))
        return render_template("edit.html", page=p)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
