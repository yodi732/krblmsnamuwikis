\
import os
from datetime import datetime
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

def _database_uri():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Render supplies a postgres:// URL sometimes; SQLAlchemy needs postgresql+psycopg
        db_url = db_url.replace("postgres://", "postgresql+psycopg://")
        return db_url
    return "sqlite:///byeolnaewiki.db"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")
db = SQLAlchemy(app)

# --------------------- Models ---------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    parent = db.relationship("Document", remote_side=[id], backref="children")
    is_legal = db.Column(db.Boolean, default=False)  # Terms / Privacy -> immutable
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # create / update / delete
    doc_title = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def _current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db.session.get(User, uid)

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _current_user():
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def _log_action(user_email, action, title):
    db.session.add(AuditLog(user_email=user_email, action=action, doc_title=title))
    db.session.commit()

# --------------------- Routes ---------------------
@app.route("/")
def index():
    # List only top-level docs, but show immediate children under each
    tops = Document.query.filter_by(parent_id=None).order_by(Document.updated_at.desc()).all()
    return render_template("index.html", tops=tops, user=_current_user())

@app.route("/docs/new", methods=["GET", "POST"])
@login_required
def doc_new():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        parent_id_raw = request.form.get("parent_id","")
        parent = None
        if parent_id_raw:
            parent = db.session.get(Document, int(parent_id_raw))
            # disallow child-of-child
            if parent and parent.parent_id is not None:
                flash("하위문서의 하위문서는 만들 수 없습니다.", "error")
                return redirect(url_for("doc_new"))
        if not title:
            flash("제목을 입력하세요.", "error")
            return redirect(url_for("doc_new"))
        doc = Document(title=title, content=content, parent=parent)
        db.session.add(doc)
        db.session.commit()
        _log_action(_current_user().email, "create", doc.title)
        return redirect(url_for("index"))
    parents = Document.query.filter_by(parent_id=None, is_legal=False).order_by(Document.title.asc()).all()
    return render_template("new_doc.html", parents=parents, user=_current_user())

@app.route("/docs/<int:doc_id>/delete", methods=["POST"])
@login_required
def doc_delete(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        abort(404)
    if doc.is_legal:
        flash("약관/정책 문서는 삭제할 수 없습니다.", "error")
        return redirect(url_for("index"))
    if request.form.get("confirm") != "1":
        flash("삭제를 취소했습니다.", "info")
        return redirect(url_for("index"))
    title = doc.title
    # delete children first
    for child in list(doc.children):
        db.session.delete(child)
    db.session.delete(doc)
    db.session.commit()
    _log_action(_current_user().email, "delete", title)
    return redirect(url_for("index"))

@app.route("/logs")
@login_required
def view_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(500).all()
    return render_template("logs.html", logs=logs, user=_current_user())

# ---------- Auth ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        pw = request.form.get("password","")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(pw):
            session["uid"] = user.id
            return redirect(request.args.get("next") or url_for("index"))
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
    return render_template("login.html", user=_current_user())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        pw = request.form.get("password","")
        pw2 = request.form.get("password2","")
        agree_terms = request.form.get("agree_terms") == "on"
        agree_privacy = request.form.get("agree_privacy") == "on"
        if not (email and pw):
            flash("이메일/비밀번호를 입력해주세요.", "error")
            return redirect(url_for("signup"))
        if pw != pw2:
            flash("비밀번호가 일치하지 않습니다.", "error")
            return redirect(url_for("signup"))
        if not (agree_terms and agree_privacy):
            flash("약관 및 개인정보처리방침에 동의해주세요.", "error")
            return redirect(url_for("signup"))
        if User.query.filter_by(email=email).first():
            flash("이미 존재하는 이메일입니다.", "error")
            return redirect(url_for("signup"))
        user = User(email=email, password_hash=generate_password_hash(pw))
        db.session.add(user)
        db.session.commit()
        session["uid"] = user.id
        return redirect(url_for("index"))
    return render_template("signup.html", user=_current_user())

@app.route("/account/delete", methods=["POST"])
@login_required
def account_delete():
    user = _current_user()
    # For demo: just log out; in real, cascade-delete ownership etc.
    session.clear()
    flash("계정이 삭제되었습니다(데모).", "info")
    return redirect(url_for("index"))

# ---------- Legal (immutable, separate docs) ----------
@app.route("/legal/terms")
def legal_terms():
    return render_template("legal_terms.html", user=_current_user())

@app.route("/legal/privacy")
def legal_privacy():
    return render_template("legal_privacy.html", user=_current_user())

# --------------------- Start ---------------------
with app.app_context():
    db.create_all()
    # Seed legal docs if missing
    if not Document.query.filter_by(is_legal=True, title="이용약관").first():
        db.session.add(Document(title="이용약관", content="약관 전문입니다.", is_legal=True))
    if not Document.query.filter_by(is_legal=True, title="개인정보처리방침").first():
        db.session.add(Document(title="개인정보처리방침", content="개인정보처리방침 전문입니다.", is_legal=True))
    db.session.commit()

