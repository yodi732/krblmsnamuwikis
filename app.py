
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

def _normalize_database_url(url: str) -> str:
    if not url:
        return "sqlite:///local.db"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

def ensure_schema_and_seed():
    db.create_all()
    if not Document.query.filter_by(title="이용약관").first():
        db.session.add(Document(title="이용약관", content=SAMPLE_TERMS))
    if not Document.query.filter_by(title="개인정보처리방침").first():
        db.session.add(Document(title="개인정보처리방침", content=SAMPLE_PRIVACY))
    db.session.commit()

def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")
    app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_database_url(os.environ.get("DATABASE_URL", "sqlite:///local.db"))
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    with app.app_context():
        ensure_schema_and_seed()

    def current_user() -> Optional["User"]:
        uid = session.get("user_id")
        return User.query.get(uid) if uid else None

    def require_login():
        if not current_user():
            flash("로그인이 필요합니다.", "error")
            return False
        return True

    app.jinja_env.globals["current_user"] = current_user

    @app.route("/")
    def index():
        parents = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
        children_map = {p.id: Document.query.filter_by(parent_id=p.id).order_by(Document.title.asc()).all() for p in parents}
        return render_template("index.html", parents=parents, children_map=children_map)

    @app.route("/signup", methods=["GET","POST"])
    def signup():
        if request.method == "POST":
            email = request.form.get("email","").strip().lower()
            password = request.form.get("password","")
            password2 = request.form.get("password2","")
            agree_terms = bool(request.form.get("agree_terms"))
            agree_privacy = bool(request.form.get("agree_privacy"))
            if not email or not password:
                flash("이메일과 비밀번호를 입력하세요.", "error"); return redirect(url_for("signup"))
            if password != password2:
                flash("비밀번호가 일치하지 않습니다.", "error"); return redirect(url_for("signup"))
            if not (agree_terms and agree_privacy):
                flash("약관/개인정보처리방침 동의가 필요합니다.", "error"); return redirect(url_for("signup"))
            if User.query.filter_by(email=email).first():
                flash("이미 존재하는 이메일입니다.", "error"); return redirect(url_for("signup"))
            user = User(email=email, password_hash=generate_password_hash(password))
            db.session.add(user); db.session.commit()
            flash("회원가입 완료. 로그인 해주세요.", "success")
            return redirect(url_for("login"))
        terms = Document.query.filter_by(title="이용약관").first()
        privacy = Document.query.filter_by(title="개인정보처리방침").first()
        return render_template("signup.html", terms=terms, privacy=privacy)

    @app.route("/login", methods=["GET","POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email","").strip().lower()
            password = request.form.get("password","")
            user = User.query.filter_by(email=email).first()
            if not user or not check_password_hash(user.password_hash, password):
                flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
                return redirect(url_for("login"))
            session["user_id"] = user.id
            flash("로그인되었습니다.", "success")
            return redirect(url_for("index"))
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("로그아웃되었습니다.", "success")
        return redirect(url_for("index"))

    @app.route("/account/delete", methods=["POST"])
    def account_delete():
        user = current_user()
        if not user: abort(403)
        db.session.delete(user); db.session.commit()
        session.clear()
        flash("계정이 삭제되었습니다.", "success")
        return redirect(url_for("index"))

    @app.route("/docs/<int:doc_id>")
    def doc_detail(doc_id: int):
        doc = Document.query.get_or_404(doc_id)
        children = Document.query.filter_by(parent_id=doc.id).order_by(Document.title.asc()).all()
        return render_template("doc_detail.html", doc=doc, children=children)

    @app.route("/docs/new", methods=["GET","POST"])
    def doc_new():
        if request.method == "POST":
            if not require_login(): return redirect(url_for("login"))
            title = request.form.get("title","").strip()
            content = request.form.get("content","").strip()
            parent_id = request.form.get("parent_id") or None
            parent_id = int(parent_id) if parent_id else None
            if not title:
                flash("제목을 입력하세요.", "error"); return redirect(url_for("doc_new"))
            if Document.query.filter_by(title=title).first():
                flash("동일한 제목의 문서가 이미 존재합니다.", "error"); return redirect(url_for("doc_new"))
            if parent_id:
                parent_doc = Document.query.get(parent_id)
                if not parent_doc or parent_doc.parent_id is not None:
                    flash("하위 문서의 하위 문서는 만들 수 없습니다.", "error"); return redirect(url_for("doc_new"))
            doc = Document(title=title, content=content, parent_id=parent_id)
            db.session.add(doc); db.session.commit()
            _log_action(current_user().email if current_user() else "(anonymous)", "create", doc.title)
            flash("문서가 생성되었습니다.", "success")
            return redirect(url_for("doc_detail", doc_id=doc.id))
        parents = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
        return render_template("doc_edit.html", mode="new", doc=None, parents=parents)

    @app.route("/docs/<int:doc_id>/edit", methods=["GET","POST"])
    def doc_edit(doc_id: int):
        doc = Document.query.get_or_404(doc_id)
        if request.method == "POST":
            if not require_login(): return redirect(url_for("login"))
            title = request.form.get("title","").strip()
            content = request.form.get("content","").strip()
            parent_id = request.form.get("parent_id") or None
            parent_id = int(parent_id) if parent_id else None
            if not title:
                flash("제목을 입력하세요.", "error"); return redirect(url_for("doc_edit", doc_id=doc.id))
            exists = Document.query.filter(Document.title == title, Document.id != doc.id).first()
            if exists:
                flash("동일한 제목의 문서가 이미 존재합니다.", "error"); return redirect(url_for("doc_edit", doc_id=doc.id))
            if parent_id:
                parent_doc = Document.query.get(parent_id)
                if not parent_doc or parent_doc.parent_id is not None:
                    flash("하위 문서의 하위 문서는 만들 수 없습니다.", "error"); return redirect(url_for("doc_edit", doc_id=doc.id))
                if parent_id == doc.id:
                    flash("자기 자신을 상위 문서로 선택할 수 없습니다.", "error"); return redirect(url_for("doc_edit", doc_id=doc.id))
            doc.title, doc.content, doc.parent_id = title, content, parent_id
            db.session.commit()
            _log_action(current_user().email if current_user() else "(anonymous)", "update", doc.title)
            flash("문서가 수정되었습니다.", "success")
            return redirect(url_for("doc_detail", doc_id=doc.id))
        parents = Document.query.filter_by(parent_id=None).filter(Document.id != doc.id).order_by(Document.title.asc()).all()
        return render_template("doc_edit.html", mode="edit", doc=doc, parents=parents)

    @app.route("/docs/<int:doc_id>/delete", methods=["POST"])
    def doc_delete(doc_id: int):
        if not require_login(): return redirect(url_for("login"))
        doc = Document.query.get_or_404(doc_id)
        Document.query.filter_by(parent_id=doc.id).update({Document.parent_id: None})
        title = doc.title
        db.session.delete(doc); db.session.commit()
        _log_action(current_user().email if current_user() else "(anonymous)", "delete", title)
        flash("문서가 삭제되었습니다.", "success")
        return redirect(url_for("index"))

    @app.route("/legal/<string:slug>")
    def legal(slug: str):
        title = "이용약관" if slug == "terms" else "개인정보처리방침"
        doc = Document.query.filter_by(title=title).first_or_404()
        return render_template("doc_detail.html", doc=doc, children=[])

    @app.route("/logs")
    def view_logs():
        if not require_login(): return redirect(url_for("login"))
        logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(500).all()
        return render_template("logs.html", logs=logs)

    return app

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

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(254), nullable=False)
    action = db.Column(db.String(32), nullable=False)  # create/update/delete
    doc_title = db.Column(db.String(180), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

SAMPLE_TERMS = """별내위키 이용약관(요약)
- 본 서비스는 교육/커뮤니티 목적입니다.
- 불법·유해·타인권리 침해 게시물 금지.
- 운영 필요 시 이용제한/삭제가 있을 수 있습니다."""

SAMPLE_PRIVACY = """개인정보처리방침(요약)
- 수집 항목: 이메일(필수)
- 목적: 계정 식별/알림
- 보관/파기: 탈퇴 시 즉시 삭제, 법령 예외 제외."""

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
