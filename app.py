import os
from datetime import datetime
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text, select
from sqlalchemy.exc import ProgrammingError, InternalError

APP_SECRET = os.getenv("SECRET_KEY", "dev-secret-change-me")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///local.db")

# Render-provided DATABASE_URL may start with postgres://; SQLAlchemy needs postgresql+psycopg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)

app = Flask(__name__)
app.config["SECRET_KEY"] = APP_SECRET
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ---------------- Models ----------------
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    pw_hash = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, unique=True)
    content = db.Column(db.Text, nullable=False, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    parent = db.relationship("Document", remote_side=[id], backref="children")

# ---------------- Utilities ----------------
from werkzeug.security import generate_password_hash, check_password_hash

def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db.session.get(User, uid)

def login_required():
    if not current_user():
        nxt = request.path
        return redirect(url_for("login", next=nxt))

# -------- Robust, idempotent migrations (each statement isolated) --------
_ran_migrations = False

def _exec_safe(sql):
    """Execute a single SQL statement in its own transaction. Ignore benign errors."""
    try:
        with db.engine.begin() as conn:
            conn.exec_driver_sql(sql)
    except (ProgrammingError, InternalError) as e:
        # Ignore duplicate column / aborted tx errors safely; each call uses a new transaction
        # so there is no lingering aborted state.
        app.logger.warning(f"Migration step ignored: {e.__class__.__name__}: {e}")

def ensure_schema_and_seed():
    # Ensure tables
    db.create_all()

    # Handle historic column rename body -> content (best effort)
    # If 'body' exists, move data then drop.
    if db.engine.url.get_backend_name().startswith("postgresql"):
        # Postgres
        _exec_safe("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='document' AND column_name='content'
                ) THEN
                    ALTER TABLE document ADD COLUMN content TEXT NOT NULL DEFAULT '';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='document' AND column_name='body'
                ) THEN
                    UPDATE document SET content = COALESCE(content, '') || COALESCE(body, '');
                    ALTER TABLE document DROP COLUMN body;
                END IF;
            END$$;
        """)
    else:
        # SQLite: use PRAGMA table_info and safe alters
        _exec_safe("ALTER TABLE document ADD COLUMN IF NOT EXISTS content TEXT DEFAULT ''")
        # Can't easily detect/drop body in sqlite without table rebuild; ignore.

    # Ensure columns exist (idempotent)
    _exec_safe("ALTER TABLE document ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE")
    _exec_safe("ALTER TABLE document ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP")
    # Backfill updated_at then set default
    try:
        with db.engine.begin() as conn:
            conn.exec_driver_sql("UPDATE document SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
            if db.engine.url.get_backend_name().startswith("postgresql"):
                conn.exec_driver_sql("ALTER TABLE document ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP")
    except Exception as e:
        app.logger.warning(f"updated_at backfill step ignored: {e}")

    _exec_safe('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS pw_hash VARCHAR(255) NOT NULL DEFAULT \'\'')

    # Seed system docs (Terms & Privacy) if missing
    def get_or_create(title, content, is_system=True):
        doc = db.session.execute(db.select(Document).where(Document.title == title)).scalar_one_or_none()
        if not doc:
            doc = Document(title=title, content=content, is_system=is_system)
            db.session.add(doc)
            db.session.commit()
        return doc

    TERMS = """<h2>이용약관</h2><p>본 서비스 이용약관의 주요 내용은 다음과 같습니다.</p><ul><li>서비스 제공 범위</li><li>계정 및 보안</li><li>금지행위</li></ul>"""
    PRIV = """<h2>개인정보처리방침</h2><p>수집 항목, 이용목적, 보관기간, 파기절차 및 이용자 권리를 명시합니다.</p>"""

    get_or_create("이용약관", TERMS, True)
    get_or_create("개인정보처리방침", PRIV, True)

@app.before_request
def _run_once():
    global _ran_migrations
    if not _ran_migrations:
        ensure_schema_and_seed()
        _ran_migrations = True

# ---------------- Routes ----------------
@app.route("/")
def home():
    items = db.session.execute(select(Document).order_by(Document.title.asc())).scalars().all()
    return render_template("home.html", items=items, me=current_user())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = db.session.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
        if user and check_password_hash(user.pw_hash, password):
            session["uid"] = user.id
            flash("로그인되었습니다.", "success")
            return redirect(request.args.get("next") or url_for("home"))
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
    return render_template("login.html", me=current_user())

@app.route("/logout")
def logout():
    session.clear()
    flash("로그아웃되었습니다.", "success")
    return redirect(url_for("home"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        agree_terms = request.form.get("agree_terms") == "on"
        agree_priv = request.form.get("agree_priv") == "on"
        if not (agree_terms and agree_priv):
            flash("약관과 개인정보처리방침에 모두 동의해야 합니다.", "error")
            return render_template("signup.html", me=current_user())

        exists = db.session.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
        if exists:
            flash("이미 가입된 이메일입니다.", "error")
            return render_template("signup.html", me=current_user())
        hashed = generate_password_hash(password)
        u = User(email=email, pw_hash=hashed)
        db.session.add(u)
        db.session.commit()
        session["uid"] = u.id
        flash("회원가입 완료!", "success")
        return redirect(url_for("home"))
    return render_template("signup.html", me=current_user())

@app.route("/create", methods=["GET", "POST"])
def create():
    if not current_user():
        return redirect(url_for("login", next=url_for("create")))
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = request.form.get("content") or ""
        parent_id = request.form.get("parent_id")
        parent = None
        if parent_id:
            parent = db.session.get(Document, int(parent_id))
            if parent and parent.parent_id:
                # Prevent grandchild creation
                flash("하위문서의 하위문서는 만들 수 없습니다.", "error")
                return render_template("doc_create.html", me=current_user(), parents=_parent_candidates())
        doc = Document(title=title, content=content, parent=parent, is_system=False)
        db.session.add(doc)
        db.session.commit()
        return redirect(url_for("doc_detail", doc_id=doc.id))
    return render_template("doc_create.html", me=current_user(), parents=_parent_candidates())

def _parent_candidates():
    # Only top-level documents can be parents (no grandchild chains)
    return db.session.execute(select(Document).where(Document.parent_id.is_(None)).order_by(Document.title)).scalars().all()

@app.route("/doc/<int:doc_id>")
def doc_detail(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        abort(404)
    # Build siblings for sidebar
    parent = doc.parent
    top = parent or doc if parent is None else parent
    # For nav like namu-wiki: show siblings (same parent) and children of current
    siblings = db.session.execute(select(Document).where(Document.parent_id == doc.parent_id).order_by(Document.title)).scalars().all()
    children = db.session.execute(select(Document).where(Document.parent_id == doc.id).order_by(Document.title)).scalars().all()
    return render_template("doc.html", me=current_user(), doc=doc, parent=parent, siblings=siblings, children=children)

@app.route("/terms")
def terms():
    doc = db.session.execute(select(Document).where(Document.title == "이용약관")).scalar_one_or_none()
    if not doc:
        abort(404)
    return redirect(url_for("doc_detail", doc_id=doc.id))

@app.route("/privacy")
def privacy():
    doc = db.session.execute(select(Document).where(Document.title == "개인정보처리방침")).scalar_one_or_none()
    if not doc:
        abort(404)
    return redirect(url_for("doc_detail", doc_id=doc.id))

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
