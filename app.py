
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Optional

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ---------- Helpers ----------

def _normalize_database_url(url: str) -> str:
    """
    Render often provides DATABASE_URL as 'postgres://'.
    SQLAlchemy 2.x w/ psycopg3 expects 'postgresql+psycopg://'.
    """
    if not url:
        return "sqlite:///local.db"
    # only rewrite scheme if it starts with postgres://
    if url.startswith("postgres://"):
        # preserve credentials/host/path
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    # If already postgresql://, add +psycopg if missing
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

def ensure_schema_and_seed():
    db.create_all()

    # Ensure Terms/Privacy system docs exist
    terms = Document.query.filter_by(title="이용약관").first()
    privacy = Document.query.filter_by(title="개인정보처리방침").first()

    if not terms:
        terms = Document(
            title="이용약관",
            content="별내위키 이용약관입니다. 본 서비스는 학습/커뮤니티 용도로 제공되며, 불법/유해 게시물 금지.",
            parent_id=None,
        )
        db.session.add(terms)
    if not privacy:
        privacy = Document(
            title="개인정보처리방침",
            content="별내위키는 계정 식별을 위해 이메일만 최소한으로 수집합니다. 요청 시 탈퇴/삭제를 보장합니다.",
            parent_id=None,
        )
        db.session.add(privacy)
    db.session.commit()

# ---------- App Factory ----------

def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Secret key
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")

    # Database URL
    raw_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_database_url(raw_url)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        ensure_schema_and_seed()

    # ---------- Routes ----------

    @app.route("/")
    def index():
        docs = Document.query.order_by(Document.created_at.desc()).all()
        return render_template("index.html", docs=docs, user=current_user())

    # ---- Auth ----

    def current_user() -> Optional["User"]:
        uid = session.get("user_id")
        if not uid:
            return None
        return User.query.get(uid)

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            agree_terms = request.form.get("agree_terms")
            agree_privacy = request.form.get("agree_privacy")

            if not email or not password:
                flash("이메일과 비밀번호를 입력하세요.", "error")
                return redirect(url_for("signup"))

            if not agree_terms or not agree_privacy:
                flash("이용약관과 개인정보 처리방침에 동의해야 가입할 수 있습니다.", "error")
                return redirect(url_for("signup"))

            if User.query.filter_by(email=email).first():
                flash("이미 존재하는 이메일입니다.", "error")
                return redirect(url_for("signup"))

            user = User(
                email=email,
                password_hash=generate_password_hash(password),
            )
            db.session.add(user)
            db.session.commit()
            flash("회원가입이 완료되었습니다. 로그인 해주세요.", "success")
            return redirect(url_for("login"))

        return render_template("signup.html", user=current_user())

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            user = User.query.filter_by(email=email).first()
            if not user or not check_password_hash(user.password_hash, password):
                flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
                return redirect(url_for("login"))

            session["user_id"] = user.id
            flash("로그인되었습니다.", "success")
            return redirect(url_for("index"))
        return render_template("login.html", user=current_user())

    @app.route("/logout")
    def logout():
        session.clear()
        flash("로그아웃되었습니다.", "success")
        return redirect(url_for("index"))

    @app.route("/account/delete", methods=["POST"])
    def account_delete():
        user = current_user()
        if not user:
            abort(403)
        # Remove user-owned documents or leave as is (wiki content is communal).
        # For safety in school setting, we'll keep documents but anonymize owner field if existed.
        db.session.delete(user)
        db.session.commit()
        session.clear()
        flash("계정이 삭제되었습니다.", "success")
        return redirect(url_for("index"))

    # ---- Documents ----

    def login_required():
        if not current_user():
            flash("로그인이 필요합니다.", "error")
            return False
        return True

    @app.route("/docs/<int:doc_id>")
    def doc_detail(doc_id: int):
        doc = Document.query.get_or_404(doc_id)
        children = Document.query.filter_by(parent_id=doc.id).all()
        return render_template("doc_detail.html", doc=doc, children=children, user=current_user())

    @app.route("/docs/new", methods=["GET", "POST"])
    def doc_new():
        if request.method == "POST":
            if not login_required():
                return redirect(url_for("login"))
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            parent_id = request.form.get("parent_id") or None
            parent_id = int(parent_id) if parent_id else None

            if not title:
                flash("제목을 입력하세요.", "error")
                return redirect(url_for("doc_new"))

            if Document.query.filter_by(title=title).first():
                flash("동일한 제목의 문서가 이미 존재합니다.", "error")
                return redirect(url_for("doc_new"))

            doc = Document(title=title, content=content, parent_id=parent_id)
            db.session.add(doc)
            db.session.commit()
            flash("문서가 생성되었습니다.", "success")
            return redirect(url_for("doc_detail", doc_id=doc.id))
        # GET
        parents = Document.query.order_by(Document.title.asc()).all()
        return render_template("doc_edit.html", mode="new", parents=parents, user=current_user())

    @app.route("/docs/<int:doc_id>/edit", methods=["GET", "POST"])
    def doc_edit(doc_id: int):
        doc = Document.query.get_or_404(doc_id)
        if request.method == "POST":
            if not login_required():
                return redirect(url_for("login"))

            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            parent_id = request.form.get("parent_id") or None
            parent_id = int(parent_id) if parent_id else None

            if not title:
                flash("제목을 입력하세요.", "error")
                return redirect(url_for("doc_edit", doc_id=doc.id))

            # check unique title (excluding current)
            exists = Document.query.filter(Document.title == title, Document.id != doc.id).first()
            if exists:
                flash("동일한 제목의 문서가 이미 존재합니다.", "error")
                return redirect(url_for("doc_edit", doc_id=doc.id))

            doc.title = title
            doc.content = content
            doc.parent_id = parent_id
            db.session.commit()
            flash("문서가 수정되었습니다.", "success")
            return redirect(url_for("doc_detail", doc_id=doc.id))
        # GET
        parents = Document.query.filter(Document.id != doc.id).order_by(Document.title.asc()).all()
        return render_template("doc_edit.html", mode="edit", doc=doc, parents=parents, user=current_user())

    @app.route("/docs/<int:doc_id>/delete", methods=["POST"])
    def doc_delete(doc_id: int):
        if not login_required():
            return redirect(url_for("login"))
        doc = Document.query.get_or_404(doc_id)
        # Re-parent children to None
        Document.query.filter_by(parent_id=doc.id).update({Document.parent_id: None})
        db.session.delete(doc)
        db.session.commit()
        flash("문서가 삭제되었습니다.", "success")
        return redirect(url_for("index"))

    # simple page for Terms/Privacy
    @app.route("/legal/<string:slug>")
    def legal(slug: str):
        title = "이용약관" if slug == "terms" else "개인정보처리방침"
        doc = Document.query.filter_by(title=title).first_or_404()
        return render_template("doc_detail.html", doc=doc, children=[], user=current_user())

    return app


# ---------- Models ----------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, default="", nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ---------- Dev entry ----------

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
