\
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

def make_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
    # Render/Heroku-style DATABASE_URL compatibility
    db_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
    # psycopg on SQLAlchemy 2.0 needs postgresql+psycopg scheme
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://","postgresql+psycopg://",1)
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://","postgresql+psycopg://",1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    return app

app = make_app()
db = SQLAlchemy(app)

# ---- Models ------------------------------------------------------------------

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    # IMPORTANT: keep password_hash as the source of truth (NOT NULL in DB)
    password_hash = db.Column(db.String(255), nullable=False)
    # Legacy column still present in some DBs; keep it nullable and unused
    pw = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)
        # do NOT persist raw password
        self.pw = None

    def check_password(self, raw: str) -> bool:
        try:
            return check_password_hash(self.password_hash, raw)
        except Exception:
            return False

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=True)
    is_system = db.Column(db.Boolean, default=False, nullable=False)  # view-only docs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ---- Hooks -------------------------------------------------------------------

@app.before_request
def load_user():
    uid = session.get("uid")
    g.user = User.query.get(uid) if uid else None

# ---- Routes ------------------------------------------------------------------

@app.get("/")
def index():
    # show non-system docs only
    docs = Document.query.filter_by(is_system=False).order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        password = request.form.get("password","")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return render_template("login.html"), 200
        session["uid"] = user.id
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("uid", None)
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        password = request.form.get("password","")

        if not email or not password:
            flash("이메일/비밀번호를 입력해 주세요.", "error")
            return render_template("signup.html"), 400

        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "error")
            return render_template("signup.html"), 409

        u = User(email=email)
        u.set_password(password)  # <- store hash into password_hash
        db.session.add(u)
        db.session.commit()
        flash("가입이 완료되었습니다. 로그인해 주세요.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")

# Legal: view-only, not listed, accessible from footer and signup page
@app.get("/legal/terms")
def legal_terms():
    return render_template("legal_terms.html")

@app.get("/legal/privacy")
def legal_privacy():
    return render_template("legal_privacy.html")

# Utilities to create initial system docs if missing
@app.cli.command("initdb")
def initdb():
    db.create_all()
    # create system docs only if not exists
    ensure_system_docs()
    print("DB initialized.")

def ensure_system_docs():
    terms = Document.query.filter_by(is_system=True, title="이용약관").first()
    privacy = Document.query.filter_by(is_system=True, title="개인정보처리방침").first()
    if not terms:
        db.session.add(Document(title="이용약관", body="", is_system=True))
    if not privacy:
        db.session.add(Document(title="개인정보처리방침", body="", is_system=True))
    db.session.commit()

# one-time automatic setup on first run for sqlite; safe on postgres
with app.app_context():
    db.create_all()
    try:
        ensure_system_docs()
    except Exception:
        # if table doesn't exist yet or other benign errors on cold boot, ignore
        pass
