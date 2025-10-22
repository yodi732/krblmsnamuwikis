import os
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///byeollae.db")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    pw = db.Column(db.String(255), nullable=False, default="")  # exists for compatibility

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, unique=True)
    content = db.Column(db.Text, nullable=False, default="")
    is_legal = db.Column(db.Boolean, nullable=False, default=False)

class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    doc_title = db.Column(db.String(255))

def ensure_schema():
    """Create tables if missing and make sure required columns exist for compatibility."""
    db.create_all()
    # Add columns if they don't exist (idempotent)
    try:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS pw VARCHAR(255)'))
    except Exception:
        db.session.rollback()
    try:
        db.session.execute(text('ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS doc_title VARCHAR(255)'))
    except Exception:
        db.session.rollback()
    try:
        db.session.execute(text('ALTER TABLE document ADD COLUMN IF NOT EXISTS is_legal BOOLEAN NOT NULL DEFAULT FALSE'))
    except Exception:
        db.session.rollback()
    db.session.commit()

@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if not uid:
        return
    try:
        g.user = db.session.get(User, uid)
    except SQLAlchemyError:
        session.pop("uid", None)
        g.user = None

def log_action(user_email, action, doc_title=None):
    try:
        db.session.add(AuditLog(user_email=user_email, action=action, doc_title=doc_title))
        db.session.commit()
    except Exception:
        db.session.rollback()

@app.get("/")
def index():
    # Exclude legal docs and well-known titles
    docs = Document.query.filter(
        Document.is_legal.is_(False),
        Document.title.notin_(["이용약관", "개인정보처리방침"])
    ).order_by(Document.id.desc()).all()
    return render_template("index.html", docs=docs)

@app.get("/docs/<int:doc_id>")
def doc_view(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        abort(404)
    return render_template("doc_view.html", doc=doc)

@app.route("/docs/new", methods=["GET","POST"])
def doc_new():
    if not g.user:
        return redirect(url_for("login"))
    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form.get("content","")
        # Prevent creating legal-titled docs
        if title in ["이용약관","개인정보처리방침"]:
            flash("해당 제목은 사용할 수 없습니다.")
            return redirect(url_for("doc_new"))
        doc = Document(title=title, content=content, is_legal=False)
        db.session.add(doc)
        db.session.commit()
        log_action(g.user.email, "create", title)
        return redirect(url_for("doc_view", doc_id=doc.id))
    return render_template("doc_form.html", form_title="새 문서", doc=None)

@app.route("/docs/<int:doc_id>/edit", methods=["GET","POST"])
def doc_edit(doc_id):
    if not g.user:
        return redirect(url_for("login"))
    doc = db.session.get(Document, doc_id)
    if not doc:
        abort(404)
    if doc.is_legal:
        abort(403)
    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form.get("content","")
        if title in ["이용약관","개인정보처리방침"]:
            flash("해당 제목은 사용할 수 없습니다.")
            return redirect(url_for("doc_edit", doc_id=doc.id))
        doc.title = title
        doc.content = content
        db.session.commit()
        log_action(g.user.email, "update", title)
        return redirect(url_for("doc_view", doc_id=doc.id))
    return render_template("doc_form.html", form_title="문서 수정", doc=doc)

@app.post("/docs/<int:doc_id>/delete")
def doc_delete(doc_id):
    if not g.user:
        return redirect(url_for("login"))
    doc = db.session.get(Document, doc_id)
    if not doc:
        abort(404)
    if doc.is_legal:
        abort(403)
    title = doc.title
    db.session.delete(doc)
    db.session.commit()
    log_action(g.user.email, "delete", title)
    return redirect(url_for("index"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if not user or not user.pw or not check_password_hash(user.pw, password):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.")
            return redirect(url_for("login"))
        session["uid"] = user.id
        log_action(user.email, "login")
        return redirect(url_for("index"))
    return render_template("login.html")

@app.post("/logout")
def logout():
    if g.user:
        log_action(g.user.email, "logout")
    session.clear()
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.")
            return redirect(url_for("signup"))
        user = User(email=email, pw=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        session["uid"] = user.id
        log_action(user.email, "signup")
        return redirect(url_for("index"))
    return render_template("signup.html")

# Legal pages: view-only, not DB-backed, not in lists
@app.get("/legal/terms")
def legal_terms():
    return render_template("legal/terms.html")

@app.get("/legal/privacy")
def legal_privacy():
    return render_template("legal/privacy.html")

with app.app_context():
    ensure_schema()
