
import os
from datetime import datetime
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = SECRET_KEY

db = SQLAlchemy(app)

# -------------------- Models --------------------
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    pw_hash = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    parent = db.relationship("Document", remote_side=[id])

# -------------------- One-time bootstrap --------------------
_boot_ran = False
@app.before_request
def _run_once():
    global _boot_ran
    if _boot_ran:
        return
    ensure_schema_and_seed()
    _boot_ran = True

def ensure_schema_and_seed():
    with db.engine.begin() as conn:
        # Create tables if not exists
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS "user"(
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                pw_hash VARCHAR(255) NOT NULL DEFAULT '',
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            );
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS document(
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                parent_id INTEGER REFERENCES document(id),
                is_system BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            );
        """)
        # Safe column adds / migrations
        # content (for older schemas that had body)
        conn.exec_driver_sql("""
            ALTER TABLE document ADD COLUMN IF NOT EXISTS content TEXT NOT NULL DEFAULT '';
        """)
        # body -> content migration (best-effort; 'body' may not exist)
        try:
            conn.exec_driver_sql("""
                UPDATE document SET content = COALESCE(content,'') || COALESCE(body,'')
            """)
            conn.exec_driver_sql("""
                ALTER TABLE document DROP COLUMN body
            """)
        except Exception:
            pass
        # is_system
        conn.exec_driver_sql("""
            ALTER TABLE document ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE;
        """)
        # updated_at
        conn.exec_driver_sql("""
            ALTER TABLE document ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;
        """)
        conn.exec_driver_sql("""
            UPDATE document SET updated_at = NOW() WHERE updated_at IS NULL;
        """)
        conn.exec_driver_sql("""
            ALTER TABLE document ALTER COLUMN updated_at SET DEFAULT NOW();
        """)
        # user.pw_hash (robust for PG/SQLite)
        conn.exec_driver_sql("""
            ALTER TABLE "user" ADD COLUMN IF NOT EXISTS pw_hash VARCHAR(255) NOT NULL DEFAULT '';
        """)

        # Seed system docs (Terms & Privacy)
        terms_id = conn.execute(text("""
            INSERT INTO document (title, content, is_system)
            VALUES (:t, :c, true)
            ON CONFLICT DO NOTHING
            RETURNING id
        """), {"t": "이용약관", "c": TERMS_CONTENT}).fetchone()
        privacy_id = conn.execute(text("""
            INSERT INTO document (title, content, is_system)
            VALUES (:t, :c, true)
            ON CONFLICT DO NOTHING
            RETURNING id
        """), {"t": "개인정보처리방침", "c": PRIVACY_CONTENT}).fetchone()

        # If RETURNING didn't produce rows because record exists, fetch ids
        if terms_id is None:
            terms_id = conn.execute(text("SELECT id FROM document WHERE title=:t"), {"t":"이용약관"}).fetchone()
        if privacy_id is None:
            privacy_id = conn.execute(text("SELECT id FROM document WHERE title=:t"), {"t":"개인정보처리방침"}).fetchone()
        app.config["TERMS_ID"] = terms_id[0] if terms_id else None
        app.config["PRIVACY_ID"] = privacy_id[0] if privacy_id else None

# -------------------- Helpers --------------------
def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return User.query.get(uid)

# -------------------- Routes --------------------
@app.route("/")
def home():
    items = Document.query.order_by(Document.title.asc()).all()
    return render_template("home.html", items=items, me=current_user())

@app.route("/doc/<int:doc_id>")
def doc_detail(doc_id):
    doc = Document.query.get_or_404(doc_id)
    # gather children (only one depth shown; child's children won't be creatable)
    children = Document.query.filter_by(parent_id=doc.id).all()
    parent = doc.parent
    return render_template("doc.html", doc=doc, parent=parent, children=children, me=current_user())

@app.route("/create", methods=["GET", "POST"], endpoint="create")
def create_doc():
    me = current_user()
    if not me:
        return redirect(url_for("login", next=request.path))
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        parent_id = request.form.get("parent_id") or None
        # block 2+ depth
        if parent_id:
            parent = Document.query.get(int(parent_id))
            if parent and parent.parent_id:
                flash("하위문서의 하위문서는 만들 수 없습니다.", "warning")
                return redirect(url_for("create"))
        if not title:
            flash("제목을 입력하세요.", "danger")
            return redirect(url_for("create"))
        doc = Document(title=title, content=request.form.get("content",""), parent_id=int(parent_id) if parent_id else None)
        db.session.add(doc)
        db.session.commit()
        return redirect(url_for("doc_detail", doc_id=doc.id))
    # show possible parents (only top-level can be parent)
    parents = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
    return render_template("create.html", parents=parents, me=me)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").lower().strip()
        password = request.form.get("password") or ""
        user = User.query.filter(func.lower(User.email)==email).first()
        if user and user.pw_hash and check_password_hash(user.pw_hash, password):
            session["uid"] = user.id
            next_url = request.args.get("next") or url_for("home")
            return redirect(next_url)
        flash("이메일 또는 비밀번호가 틀렸습니다.", "danger")
    return render_template("login.html", me=current_user())

@app.route("/logout")
def logout():
    session.pop("uid", None)
    return redirect(url_for("home"))

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").lower().strip()
        password = request.form.get("password") or ""
        agree_terms = request.form.get("agree_terms")
        agree_privacy = request.form.get("agree_privacy")
        if not (agree_terms and agree_privacy):
            flash("약관 및 개인정보처리방침에 모두 동의해야 합니다.", "danger")
            return redirect(url_for("signup"))
        if not email or not password:
            flash("이메일과 비밀번호를 입력하세요.", "danger")
            return redirect(url_for("signup"))
        if User.query.filter(func.lower(User.email)==email).first():
            flash("이미 가입된 이메일입니다.", "warning")
            return redirect(url_for("signup"))
        user = User(email=email, pw_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        session["uid"] = user.id
        return redirect(url_for("home"))
    return render_template("signup.html",
                           terms_id=app.config.get("TERMS_ID"),
                           privacy_id=app.config.get("PRIVACY_ID"),
                           me=current_user())

@app.route("/terms")
def terms():
    tid = app.config.get("TERMS_ID")
    if not tid:
        abort(404)
    return redirect(url_for("doc_detail", doc_id=tid))

@app.route("/privacy")
def privacy():
    pid = app.config.get("PRIVACY_ID")
    if not pid:
        abort(404)
    return redirect(url_for("doc_detail", doc_id=pid))

# -------------------- Constants (seed content) --------------------
TERMS_CONTENT = """
제1조(목적) 이 약관은 서비스 이용에 관한 기본적인 사항을 규정합니다.

제2조(가입) 회원은 이메일과 비밀번호를 등록하여 가입합니다.

제3조(의무) 회원은 법령과 본 약관을 준수합니다.
"""

PRIVACY_CONTENT = """
1. 수집항목: 이메일, 비밀번호 해시
2. 이용목적: 회원 가입 및 서비스 제공
3. 보관기간: 탈퇴 시까지 또는 관계 법령에 따름
"""

# -------------------- Dev entry --------------------
if __name__ == "__main__":
    # Simple dev server
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
