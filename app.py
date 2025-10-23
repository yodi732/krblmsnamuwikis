import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

def _pg_uri():
    uri = os.getenv("DATABASE_URL", "").strip()
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql+psycopg://", 1)
    elif uri.startswith("postgresql://") and "+psycopg" not in uri:
        uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
    return uri

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-prod")
app.config["SQLALCHEMY_DATABASE_URI"] = _pg_uri() or "sqlite:///local.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = db.session.get(User, uid)

def login_required():
    if not g.user:
        flash("로그인이 필요합니다.", "warn")
        return redirect(url_for("login", next=request.path))

@app.get("/")
def index():
    docs = Document.query.filter_by(is_system=False).order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.get("/doc/new")
def doc_new():
    if not g.user:
        return login_required()
    return render_template("document_edit.html", doc=None)

@app.post("/doc/new")
def doc_create():
    if not g.user:
        return login_required()
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    if not title or not content:
        flash("제목과 내용을 입력해주세요.", "error")
        return render_template("document_edit.html", doc=None, title=title, content=content)
    d = Document(title=title, content=content, is_system=False)
    db.session.add(d)
    db.session.commit()
    return redirect(url_for("doc_view", doc_id=d.id))

@app.get("/doc/<int:doc_id>")
def doc_view(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    if doc.is_system:
        abort(404)
    return render_template("document_view.html", doc=doc)

@app.get("/doc/<int:doc_id>/edit")
def doc_edit(doc_id):
    if not g.user:
        return login_required()
    doc = db.session.get(Document, doc_id) or abort(404)
    if doc.is_system:
        abort(403)
    return render_template("document_edit.html", doc=doc)

@app.post("/doc/<int:doc_id>/edit")
def doc_update(doc_id):
    if not g.user:
        return login_required()
    doc = db.session.get(Document, doc_id) or abort(404)
    if doc.is_system:
        abort(403)
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    if not title or not content:
        flash("제목과 내용을 입력해주세요.", "error")
        return render_template("document_edit.html", doc=doc, title=title, content=content)
    doc.title = title
    doc.content = content
    db.session.commit()
    return redirect(url_for("doc_view", doc_id=doc.id))

@app.post("/doc/<int:doc_id>/delete")
def doc_delete(doc_id):
    if not g.user:
        return login_required()
    doc = db.session.get(Document, doc_id) or abort(404)
    if doc.is_system:
        abort(403)
    db.session.delete(doc)
    db.session.commit()
    flash("삭제되었습니다.", "ok")
    return redirect(url_for("index"))

@app.get("/login")
def login():
    return render_template("login.html")

@app.post("/login")
def login_post():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    user = User.query.filter(func.lower(User.email)==email).first()
    if not user or not user.check_password(password):
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
        return render_template("login.html"), 200
    session["uid"] = user.id
    next_url = request.args.get("next") or url_for("index")
    return redirect(next_url)

@app.get("/logout")
def logout():
    session.pop("uid", None)
    return redirect(url_for("index"))

@app.get("/signup")
def signup():
    return render_template("signup.html")

@app.post("/signup")
def signup_post():
    email = (request.form.get("email") or "").strip().lower()
    pw = request.form.get("password") or ""
    pw2 = request.form.get("password2") or ""
    agree = request.form.get("agree") == "on"
    if not email or not pw or not pw2:
        flash("모든 필드를 입력해주세요.", "error")
        return render_template("signup.html"), 200
    if pw != pw2:
        flash("비밀번호 확인이 일치하지 않습니다.", "error")
        return render_template("signup.html"), 200
    if not agree:
        flash("약관 및 개인정보처리방침에 동의가 필요합니다.", "error")
        return render_template("signup.html"), 200
    if User.query.filter(func.lower(User.email)==email).first():
        flash("이미 가입된 이메일입니다.", "error")
        return render_template("signup.html"), 200
    u = User(email=email)
    u.set_password(pw)
    db.session.add(u)
    db.session.commit()
    session["uid"] = u.id
    return redirect(url_for("index"))

@app.get("/legal/terms")
def legal_terms():
    return render_template("legal_terms.html")

@app.get("/legal/privacy")
def legal_privacy():
    return render_template("legal_privacy.html")

@app.get("/healthz")
def healthz():
    return {"ok": True, "time": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)