import os
from datetime import datetime, timezone

from flask import Flask, render_template, request, redirect, url_for, session, g, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

def _normalize_db_url(url: str) -> str:
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return url

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_db_url(os.environ.get("DATABASE_URL", "sqlite:///local.db"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    pw = db.synonym("password_hash")

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw or "")

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    # FIX: map attribute 'body' to actual DB column 'content'
    body = db.Column("content", db.Text, nullable=False)
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

@app.before_request
def load_user():
    uid = session.get("uid")
    g.user = User.query.get(uid) if uid else None

@app.route("/")
def index():
    docs = Document.query.filter_by(is_system=False).order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        pw = request.form.get("pw") or request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(pw):
            session["uid"] = user.id
            return redirect(url_for("index"))
        return render_template("login.html", error="이메일 또는 비밀번호가 올바르지 않습니다.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        pw = request.form.get("pw") or request.form.get("password") or ""
        if not email or not pw:
            return render_template("signup.html", error="이메일/비밀번호를 입력해주세요.")
        if User.query.filter_by(email=email).first():
            return render_template("signup.html", error="이미 가입된 이메일입니다.")
        user = User(email=email)
        user.set_password(pw)
        db.session.add(user)
        db.session.commit()
        session["uid"] = user.id
        return redirect(url_for("index"))
    return render_template("signup.html")

@app.route("/legal/terms")
def legal_terms():
    doc = Document.query.filter_by(is_system=True, title="이용약관").order_by(Document.created_at.desc()).first()
    return render_template("terms.html", doc=doc)

@app.route("/legal/privacy")
def legal_privacy():
    doc = Document.query.filter_by(is_system=True, title="개인정보처리방침").order_by(Document.created_at.desc()).first()
    return render_template("privacy.html", doc=doc)

@app.route("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
