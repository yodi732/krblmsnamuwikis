import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")
db_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL env var is required")
# Render adds ?sslmode= to DATABASE_URL sometimes; ensure it stays.
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- Models ---
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=False)
    pw_hash = db.Column(db.String)  # added via migration if missing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    content = db.Column(db.Text, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_system = db.Column(db.Boolean, default=False, nullable=False)

# --- helpers ---
def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db.session.get(User, uid)

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            nxt = request.path
            return redirect(url_for("login", next=nxt))
        return f(*args, **kwargs)
    return wrapper

@app.before_request
def load_user():
    g.user = current_user()

# --- bootstrap/migrations ---
with app.app_context():
    # Ensure base tables exist (user may not exist yet)
    db.create_all()
    # Hardening: add pw_hash if missing (prevents 500 during login)
    db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS pw_hash VARCHAR'))
    db.session.execute(text('ALTER TABLE "user" ALTER COLUMN created_at SET DEFAULT NOW()'))
    # Document safety: ensure updated_at default
    db.session.execute(text('ALTER TABLE document ALTER COLUMN updated_at SET DEFAULT NOW()'))
    db.session.commit()
    # Seed system docs if missing
    def seed_once(title, body):
        exists = Document.query.filter_by(title=title, is_system=True).first()
        if not exists:
            d = Document(title=title, content=body, is_system=True)
            db.session.add(d)
            db.session.commit()
    seed_once("이용약관", "본 서비스는 교육 목적으로 운영되며... (여기에 약관 본문을 저장하세요)")
    seed_once("개인정보처리방침", "본 위키는 서비스 제공에 필요한 최소한의 개인정보만을 수집·이용합니다... (본문)")

# --- routes ---
@app.route("/")
def home():
    def walk(node, depth, out):
        out.append((node, depth))
        children = Document.query.filter_by(parent_id=node.id).order_by(Document.title.asc()).all()
        for ch in children:
            walk(ch, depth+1, out)

    items = []
    roots = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
    for r in roots:
        walk(r, 0, items)
    return render_template("home.html", items=items, me=current_user())

@app.route("/doc/<int:doc_id>")
def view_doc(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    children = Document.query.filter_by(parent_id=doc.id).order_by(Document.title.asc()).all()
    parent = db.session.get(Document, doc.parent_id) if doc.parent_id else None
    return render_template("view.html", doc=doc, parent=parent, children=children, me=current_user())

@app.route("/terms")
def terms():
    # redirect to system doc '이용약관', fallback: home
    d = Document.query.filter_by(title="이용약관", is_system=True).first()
    return redirect(url_for("view_doc", doc_id=d.id)) if d else redirect(url_for("home"))

@app.route("/privacy")
def privacy():
    d = Document.query.filter_by(title="개인정보처리방침", is_system=True).first()
    return redirect(url_for("view_doc", doc_id=d.id)) if d else redirect(url_for("home"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if not user or not user.pw_hash or not check_password_hash(user.pw_hash, pw):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return redirect(url_for("login", next=request.args.get("next") or ""))
        session["uid"] = user.id
        return redirect(request.args.get("next") or url_for("home"))
    return render_template("login.html", me=current_user())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        agree_terms = request.form.get("agree_terms") == "on"
        agree_priv = request.form.get("agree_privacy") == "on"

        if not email.endswith("@bl-m.kr"):
            flash("학교 이메일(@bl-m.kr)만 가입 가능합니다.", "error")
            return redirect(url_for("signup"))

        if not (agree_terms and agree_priv):
            flash("약관 및 개인정보처리방침 동의가 필요합니다.", "error")
            return redirect(url_for("signup"))

        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "error")
            return redirect(url_for("login"))

        pw_hash = generate_password_hash(password)
        user = User(email=email, pw_hash=pw_hash)
        db.session.add(user)
        db.session.commit()
        session["uid"] = user.id
        return redirect(url_for("home"))
    # Load snippets for display
    terms_doc = Document.query.filter_by(title="이용약관", is_system=True).first()
    privacy_doc = Document.query.filter_by(title="개인정보처리방침", is_system=True).first()
    return render_template("signup.html", terms=terms_doc, privacy=privacy_doc, me=current_user())

@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        title = request.form.get("title") or ""
        content = request.form.get("content") or ""
        parent_id = request.form.get("parent_id") or None
        parent_id = int(parent_id) if parent_id else None
        d = Document(title=title, content=content, parent_id=parent_id, is_system=False)
        db.session.add(d)
        db.session.commit()
        return redirect(url_for("view_doc", doc_id=d.id))
    parents = Document.query.order_by(Document.title.asc()).all()
    return render_template("create.html", parents=parents, me=current_user())

@app.route("/logs")
@login_required
def logs():
    # Placeholder for activity logs page (restricted)
    return render_template("logs.html", me=current_user())

@app.post("/delete_account")
@login_required
def delete_account():
    # erase user immediately (minimal data model)
    u = current_user()
    session.clear()
    db.session.delete(u)
    db.session.commit()
    flash("회원 탈퇴가 완료되었습니다.", "info")
    return redirect(url_for("home"))

# For Render
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
