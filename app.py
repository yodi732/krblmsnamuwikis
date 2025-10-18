from __future__ import annotations
import os, re, ipaddress, datetime as dt
from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import func, UniqueConstraint
from werkzeug.security import generate_password_hash, check_password_hash

from flask_login import (
    LoginManager, login_user, login_required, logout_user,
    current_user, UserMixin
)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app.db")
if DATABASE_URL.startswith("postgresql://"):
    # SQLAlchemy 2.0 + psycopg3 prefers postgresql+psycopg
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# ------------- Models -------------
class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    ip_masked = db.Column(db.String(64), nullable=False)
    action = db.Column(db.String(64), nullable=False)
    meta = db.Column(db.Text, nullable=True)

    @staticmethod
    def write(action: str, meta: str = ""):
        db.session.add(Log(ip_masked=mask_ip(get_ip()), action=action, meta=meta))
        db.session.commit()


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    slug = db.Column(db.String(64), unique=True, nullable=True)  # special pages (terms/privacy)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

    parent = relationship("Document", remote_side=[id], backref="children")

    __table_args__ = (
        UniqueConstraint("parent_id", "title", name="uq_parent_title"),
    )


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False)
    pw_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

    consents = relationship("UserConsent", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, raw: str):
        self.pw_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.pw_hash, raw)


class TermsVersion(db.Model):
    __tablename__ = "terms_version"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(32), nullable=False)  # 'terms' or 'privacy'
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("slug", "version", name="uq_slug_version"),)


class UserConsent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    slug = db.Column(db.String(32), nullable=False)  # 'terms' or 'privacy'
    version = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="consents")


# ------------- Helpers -------------
def get_ip():
    if "X-Forwarded-For" in request.headers:
        return request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr
    return request.remote_addr or "0.0.0.0"


def mask_ip(ip: str) -> str:
    try:
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.version == 4:
            parts = ip.split(".")
            parts[-1] = "0"
            return ".".join(parts)
        else:
            # zero the last 64 bits
            return str(ip_obj.supernet(prefixlen_diff=64).network_address) + "::"
    except Exception:
        return "0.0.0.0"


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# ------------- Routes (public) -------------
@app.route("/")
def index():
    # show list & a table of contents-like box (parents = those with parent_id is null)
    parents = Document.query.filter_by(parent_id=None).order_by(Document.created_at.desc()).all()
    latest = Document.query.order_by(Document.created_at.desc()).limit(20).all()
    return render_template("index.html", parents=parents, latest=latest)


@app.route("/doc/<int:doc_id>")
def view_document(doc_id: int):
    d = db.session.get(Document, doc_id) or abort(404)
    return render_template("document.html", d=d)


@app.route("/p/<slug>")
def view_doc_by_slug(slug: str):
    d = Document.query.filter_by(slug=slug).first_or_404()
    return render_template("document.html", d=d)


@app.get("/healthz")
def healthz():
    return "ok"


# ------------- Routes (document CRUD, login required) -------------
@app.post("/add/<title>")
@login_required
def add_document(title: str):
    title = title.strip()
    if not title:
        abort(400)
    d = Document(title=title, content="")
    db.session.add(d)
    db.session.commit()
    Log.write("doc_create", title)
    flash("문서를 만들었습니다.", "success")
    return redirect(url_for("view_document", doc_id=d.id))


@app.post("/doc/<int:doc_id>/edit")
@login_required
def edit_document(doc_id: int):
    d = db.session.get(Document, doc_id) or abort(404)
    content = request.form.get("content", "")
    title = request.form.get("title", "").strip() or d.title
    d.title = title
    d.content = content
    db.session.commit()
    Log.write("doc_edit", f"id={doc_id}")
    flash("저장했습니다.", "success")
    return redirect(url_for("view_document", doc_id=doc_id))


@app.post("/doc/<int:doc_id>/delete")
@login_required
def delete_document(doc_id: int):
    d = db.session.get(Document, doc_id) or abort(404)
    db.session.delete(d)
    db.session.commit()
    Log.write("doc_delete", f"id={doc_id}")
    flash("삭제했습니다.", "success")
    return redirect(url_for("index"))


# ------------- Auth -------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        agree = request.form.get("agree_terms") == "1"
        if not username or not password:
            flash("아이디/비밀번호를 입력하세요.", "danger")
            return redirect(url_for("signup"))
        if not agree:
            flash("약관과 개인정보처리방침에 동의해 주세요.", "danger")
            return redirect(url_for("signup"))

        if User.query.filter(func.lower(User.username) == username.lower()).first():
            flash("이미 존재하는 아이디입니다.", "danger")
            return redirect(url_for("signup"))

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # get id

        # record consent to current versions
        for slug in ("terms", "privacy"):
            v = current_terms_version(slug)
            db.session.add(UserConsent(user_id=user.id, slug=slug, version=v))

        db.session.commit()
        login_user(user)
        flash("가입되었습니다.", "success")
        return redirect(url_for("index"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if not user or not user.check_password(password):
            flash("아이디 또는 비밀번호가 올바르지 않습니다.", "danger")
            return redirect(url_for("login"))
        login_user(user)
        flash("로그인되었습니다.", "success")
        return redirect(url_for("index"))
    return render_template("login.html")


@app.get("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("로그아웃되었습니다.", "info")
    return redirect(url_for("index"))


@app.get("/account")
@login_required
def account():
    return render_template("account.html")


@app.post("/account/delete")
@login_required
def delete_account():
    uid = current_user.id
    logout_user()
    user = db.session.get(User, uid)
    if user:
        db.session.delete(user)
        db.session.commit()
    flash("회원탈퇴가 완료되었습니다.", "info")
    return redirect(url_for("index"))


# ------------- Logs (login required) -------------
@app.get("/logs")
@login_required
def logs():
    rows = Log.query.order_by(Log.id.desc()).limit(200).all()
    return render_template("logs.html", rows=rows)


# ------------- Terms/Privacy seed + util -------------
TERMS_BODY = """\
# 이용약관

여기에 약관을 작성하세요. 이 문서는 slug=`terms` 로 고정됩니다.
"""
PRIVACY_BODY = """\
# 개인정보처리방침

여기에 개인정보처리방침을 작성하세요. 이 문서는 slug=`privacy` 로 고정됩니다.
"""

def ensure_terms_pages():
    for slug, title, body in (
        ("terms", "이용약관", TERMS_BODY),
        ("privacy", "개인정보처리방침", PRIVACY_BODY),
    ):
        d = Document.query.filter_by(slug=slug).first()
        if not d:
            d = Document(title=title, content=body, slug=slug)
            db.session.add(d)
            db.session.commit()
    # ensure version rows
    for slug in ("terms", "privacy"):
        if not TermsVersion.query.filter_by(slug=slug).first():
            db.session.add(TermsVersion(slug=slug, version=1))
    db.session.commit()


def current_terms_version(slug: str) -> int:
    tv = TermsVersion.query.filter_by(slug=slug).order_by(TermsVersion.version.desc()).first()
    return tv.version if tv else 1


# ------------- Bootstrap -------------
with app.app_context():
    db.create_all()
    ensure_terms_pages()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
