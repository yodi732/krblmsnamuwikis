from __future__ import annotations
import os
from datetime import datetime
import re
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = SECRET_KEY

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    author_email = db.Column(db.String(255), nullable=True)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), nullable=True, index=True)
    action = db.Column(db.String(64), nullable=False)
    target = db.Column(db.String(255), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

BL_DOMAIN = "@bl-m.kr"
EMAIL_REGEX = re.compile(rf"^[A-Za-z0-9._%+-]+{re.escape(BL_DOMAIN)}$")

def is_school_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email or ""))

def log(action: str, target: str|None=None, details: str|None=None):
    try:
        entry = Log(
            user_email=(current_user.email if current_user.is_authenticated else None),
            action=action,
            target=target,
            details=details,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def init_db():
    db.create_all()
    engine = db.engine
    if engine.url.drivername.startswith("postgresql"):
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE IF EXISTS document ADD COLUMN IF NOT EXISTS author_email VARCHAR(255);"))
            conn.execute(text("ALTER TABLE IF EXISTS log ADD COLUMN IF NOT EXISTS target VARCHAR(255);"))

with app.app_context():
    init_db()

@app.route("/")
def index():
    docs = Document.query.order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.route("/logs")
@login_required
def logs():
    rows = Log.query.order_by(Log.created_at.desc()).limit(500).all()
    return render_template("logs.html", rows=rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            login_user(user)
            log("login", target="user", details=f"{email} logged in")
            flash("로그인 되었습니다.", "success")
            return redirect(url_for("index"))
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
    return render_template("auth/login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        agree = request.form.get("agree") == "on"
        if not agree:
            flash("개인정보 처리 및 이용약관에 동의해야 가입할 수 있습니다.", "error")
            return render_template("auth/register.html", email=email)
        if not is_school_email(email):
            flash(f"학교 계정(@{BL_DOMAIN[1:]})만 가입할 수 있습니다.", "error")
            return render_template("auth/register.html", email=email)
        if not password or len(password) < 6:
            flash("비밀번호는 6자 이상이어야 합니다.", "error")
            return render_template("auth/register.html", email=email)
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "error")
            return render_template("auth/register.html", email=email)
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()
        log("register", target="user", details=f"{email} registered")
        login_user(user)
        flash("회원가입이 완료되었습니다. 자동으로 로그인되었습니다.", "success")
        return redirect(url_for("index"))
    return render_template("auth/register.html")

@app.route("/logout")
@login_required
def logout():
    email = current_user.email
    logout_user()
    log("logout", target="user", details=f"{email} logged out")
    flash("로그아웃 되었습니다.", "success")
    return redirect(url_for("index"))

@app.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    email = current_user.email
    uid = current_user.id
    logout_user()
    user = db.session.get(User, uid)
    if user:
        db.session.delete(user)
        db.session.commit()
    log("delete_account", target="user", details=f"{email} deleted account")
    flash("회원탈퇴가 완료되었습니다.", "success")
    return redirect(url_for("index"))

@app.route("/documents/create", methods=["POST"])
@login_required
def create_document():
    title = request.form.get("title","").strip()
    content = request.form.get("content","").strip()
    parent_id = request.form.get("parent_id")
    parent_id = int(parent_id) if parent_id else None
    if not title:
        flash("제목은 필수입니다.", "error")
        return redirect(url_for("index"))
    doc = Document(title=title, content=content, parent_id=parent_id, author_email=current_user.email)
    db.session.add(doc)
    db.session.commit()
    log("create_document", target=title, details=f"by {current_user.email}")
    flash("문서가 생성되었습니다.", "success")
    return redirect(url_for("index"))

@app.get("/healthz")
def healthz():
    return {"ok": True, "time": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    app.run(debug=True)
