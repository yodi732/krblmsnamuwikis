import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, g, abort, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///local.db"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SECRET_KEY","dev-secret")

db = SQLAlchemy(app)

# ---------- Models ----------
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    # The actual DB column is password_hash. Some legacy schemas may also still have 'pw' (ignored).
    password_hash = db.Column(db.String(255), nullable=False, name="password_hash")
    # Legacy column 'pw' may still exist in DB; include mapping as a deferred column if present to avoid writes.
    # Declare it as a column with custom key so ORM won't use it unless explicitly touched.
    try:
        pw = db.Column("pw", db.String(255), nullable=True)
    except Exception:
        # if the DB doesn't have pw, ignore
        pass
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    terms_agreed_at = db.Column(db.DateTime, nullable=True)
    privacy_agreed_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)


class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    # In production DB the column name is likely 'content' (not 'body'). Map it explicitly.
    body = db.Column("content", db.Text, nullable=False)
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

# ---------- Helpers ----------
@app.before_request
def load_user():
    uid = session.get("uid")
    g.user = User.query.get(uid) if uid else None

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

# ---------- Routes ----------
@app.get("/")
def index():
    # Exclude system documents (e.g., legal pages)
    docs = Document.query.filter_by(is_system=False).order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.get("/login")
def login():
    return render_template("login.html", error=None)

@app.post("/login")
def login_post():
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    user = User.query.filter_by(email=email).first()
    error = None
    if not user or not user.check_password(password):
        error = "이메일 또는 비밀번호가 올바르지 않습니다."
        return render_template("login.html", error=error), 200
    session["uid"] = user.id
    return redirect(url_for("index"))

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.get("/signup")
def signup():
    return render_template("signup.html", error=None)

@app.post("/signup")
def signup_post():
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    terms = request.form.get("agree_terms")
    privacy = request.form.get("agree_privacy")
    if not email or not password or not terms or not privacy:
        return render_template("signup.html", error="필수 항목을 모두 체크해 주세요.")
    if User.query.filter_by(email=email).first():
        return render_template("signup.html", error="이미 가입된 이메일입니다.")
    user = User(email=email)
    user.set_password(password)   # ✅ ensures password_hash column is filled
    user.terms_agreed_at = datetime.utcnow()
    user.privacy_agreed_at = datetime.utcnow()
    db.session.add(user)
    db.session.commit()
    session["uid"] = user.id
    return redirect(url_for("index"))

# Legal view-only pages (not listed in docs)
@app.get("/legal/terms")
def terms():
    return render_template("terms.html")

@app.get("/legal/privacy")
def privacy():
    return render_template("privacy.html")

# Minimal document CRUD for completeness
@app.get("/doc/<int:doc_id>")
def doc_view(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.is_system:
        abort(404)
    return render_template("doc.html", doc=doc)

@app.get("/doc/new")
@login_required
def doc_new():
    return render_template("edit.html", doc=None)

@app.post("/doc/new")
@login_required
def doc_create():
    title = request.form.get("title","").strip()
    body = request.form.get("body","").strip()
    if not title or not body:
        return render_template("edit.html", doc=None, error="제목과 내용을 입력하세요.")
    d = Document(title=title, body=body, is_system=False)
    db.session.add(d)
    db.session.commit()
    return redirect(url_for("index"))

@app.get("/doc/<int:doc_id>/edit")
@login_required
def doc_edit(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.is_system:
        abort(404)
    return render_template("edit.html", doc=doc)

@app.post("/doc/<int:doc_id>/edit")
@login_required
def doc_update(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.is_system:
        abort(404)
    doc.title = request.form.get("title","").strip()
    doc.body = request.form.get("body","").strip()
    db.session.commit()
    return redirect(url_for("doc_view", doc_id=doc.id))

# ---------- CLI utility for local testing ----------
@app.cli.command("initdb")
def initdb():
    db.create_all()
    print("DB initialized")

if __name__ == "__main__":
    app.run(debug=True)
