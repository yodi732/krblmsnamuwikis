
import os, re
from datetime import datetime
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func
from werkzeug.security import generate_password_hash, check_password_hash

def _db_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return url or "sqlite:///app.db"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY","dev")

db = SQLAlchemy(app)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(200), nullable=True, unique=False)
    content = db.Column(db.Text, nullable=False, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship("Document", remote_side=[id])

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    pw_hash = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def current_user():
    uid = session.get("uid")
    if not uid: return None
    return db.session.get(User, uid)

# ---------- DB bootstrap & seed ----------
_boot_done = False

TERMS = """<h3>이용약관</h3><p>서비스 이용과 관련한 기본 약관입니다. 회원의 의무, 금지행위, 책임 제한 등을 포함합니다.</p>"""
PRIVACY = """<h3>개인정보처리방침</h3><p>수집 항목, 이용 목적, 보관 기간, 제3자 제공, 파기 절차, 이용자 권리 등을 안내합니다.</p>"""

def ensure_schema_and_seed():
    # create tables
    db.create_all()

    # add missing columns (safe on sqlite/postgres)
    with db.engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE document ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE;
        """))
        conn.execute(text("""
            ALTER TABLE document ADD COLUMN IF NOT EXISTS slug VARCHAR(200);
        """))
        conn.execute(text("""
            ALTER TABLE "user" ADD COLUMN IF NOT EXISTS pw_hash VARCHAR(255) NOT NULL DEFAULT '';
        """))

    # de-duplicate by title for system docs
    def dedup_title(title:str):
        rows = db.session.execute(db.select(Document).where(Document.title==title)).scalars().all()
        if len(rows) <= 1:
            return rows[0] if rows else None
        # keep oldest
        rows = sorted(rows, key=lambda r: r.id)
        keep, drop = rows[0], rows[1:]
        for r in drop:
            if (r.content or "").strip() and not (keep.content or "").strip():
                keep.content = r.content
            db.session.delete(r)
        db.session.commit()
        return keep

    def get_or_create(title:str, html:str, system:bool):
        existed = db.session.execute(db.select(Document).where(Document.title==title)).scalars().all()
        if len(existed) == 1:
            doc = existed[0]
        elif len(existed) > 1:
            doc = dedup_title(title) or existed[0]
        else:
            doc = Document(title=title, is_system=system)
            db.session.add(doc)
            db.session.commit()
        # update content/system flag if empty or system requested
        doc.is_system = system or doc.is_system
        if not (doc.content or "").strip():
            doc.content = html
        if not doc.slug:
            # simple slug from title
            slug = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", title).strip("-").lower()
            doc.slug = slug[:200]
        db.session.commit()
        return doc

    terms = get_or_create("이용약관", TERMS, True)
    privacy = get_or_create("개인정보처리방침", PRIVACY, True)

@app.before_request
def _run_once():
    global _boot_done
    if not _boot_done:
        ensure_schema_and_seed()
        _boot_done = True

# ---------- Routes ----------
@app.route("/")
def home():
    items = db.session.execute(db.select(Document).order_by(Document.updated_at.desc()).limit(20)).scalars().all()
    return render_template("home.html", items=items, me=current_user())

@app.route("/docs")
def list_docs():
    items = db.session.execute(db.select(Document).order_by(Document.title.asc())).scalars().all()
    return render_template("home.html", items=items, me=current_user())

@app.route("/doc/<int:doc_id>")
def view(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    parent = db.session.get(Document, doc.parent_id) if doc.parent_id else None
    children = db.session.execute(db.select(Document).where(Document.parent_id==doc.id).order_by(Document.title)).scalars().all()
    siblings = []
    if parent:
        siblings = db.session.execute(db.select(Document).where(Document.parent_id==parent.id).order_by(Document.title)).scalars().all()
    return render_template("doc_view.html", doc=doc, parent=parent, children=children, siblings=siblings, me=current_user())

@app.route("/terms")
def terms_page():
    doc = db.session.execute(db.select(Document).where(Document.title=="이용약관")).scalars().first()
    if not doc: abort(404)
    return redirect(url_for("view", doc_id=doc.id))

@app.route("/privacy")
def privacy_page():
    doc = db.session.execute(db.select(Document).where(Document.title=="개인정보처리방침")).scalars().first()
    if not doc: abort(404)
    return redirect(url_for("view", doc_id=doc.id))

@app.route("/create", methods=["GET","POST"])
def create():
    if request.method == "GET":
        parents = db.session.execute(db.select(Document).where(Document.parent_id.is_(None)).order_by(Document.title)).scalars().all()
        return render_template("create.html", parents=parents, me=current_user())
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    parent_id = request.form.get("parent_id") or None
    if not title:
        return render_template("create.html", error="제목은 필수입니다.", parents=[], me=current_user())
    parent = db.session.get(Document, int(parent_id)) if parent_id else None
    # block second-level children
    if parent and parent.parent_id:
        return render_template("create.html", error="하위 문서의 하위 문서는 만들 수 없습니다.", parents=[], me=current_user())
    doc = Document(title=title, content=content, parent_id=parent.id if parent else None)
    db.session.add(doc)
    db.session.commit()
    return redirect(url_for("view", doc_id=doc.id))

# --------- Auth ----------
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html", me=current_user())
    email = (request.form.get("email") or "").strip().lower()
    pw = request.form.get("password") or ""
    if not email or not pw:
        return render_template("signup.html", error="이메일/비밀번호를 입력하세요.", me=current_user())
    if db.session.execute(db.select(User).where(func.lower(User.email)==email)).scalar_one_or_none():
        return render_template("signup.html", error="이미 가입된 이메일입니다.", me=current_user())
    u = User(email=email, pw_hash=generate_password_hash(pw))
    db.session.add(u)
    db.session.commit()
    session["uid"] = u.id
    return redirect(url_for("home"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", me=current_user())
    email = (request.form.get("email") or "").strip().lower()
    pw = request.form.get("password") or ""
    u = db.session.execute(db.select(User).where(func.lower(User.email)==email)).scalar_one_or_none()
    if not u or not check_password_hash(u.pw_hash, pw):
        return render_template("login.html", error="이메일 또는 비밀번호가 올바르지 않습니다.", me=current_user())
    session["uid"] = u.id
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("uid", None)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
