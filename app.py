import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# DB config (Render: DATABASE_URL / local: sqlite)
db_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
# Render postgres sometimes uses "postgres://" prefix; SQLAlchemy v2 expects "postgresql://"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------- Models ----------
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=False)
    pw_hash = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_system = db.Column(db.Boolean, default=False, nullable=False)

# ---------- Helpers ----------
def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("uid"):
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrapper

def ensure_schema_and_seed():
    with db.engine.begin() as conn:
        # Create tables if not exist
        db.Model.metadata.create_all(bind=conn)

        # 1) user table normalization: use only pw_hash
        conn.execute(text("""
        ALTER TABLE "user" ADD COLUMN IF NOT EXISTS pw_hash VARCHAR;
        """))
        conn.execute(text("""
        UPDATE "user"
           SET pw_hash = password_hash
         WHERE pw_hash IS NULL AND password_hash IS NOT NULL;
        """))
        conn.execute(text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                 WHERE table_name='user' AND column_name='password_hash'
            ) THEN
                ALTER TABLE "user" DROP COLUMN password_hash;
            END IF;
        END $$;
        """))
        conn.execute(text("""
        -- make sure not null
        UPDATE "user" SET pw_hash = '' WHERE pw_hash IS NULL;
        """))
        try:
            conn.execute(text("""ALTER TABLE "user" ALTER COLUMN pw_hash SET NOT NULL;"""))
        except Exception:
            pass

        # 2) document table add is_system if not exists
        conn.execute(text("""
        ALTER TABLE document ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE;
        """))

        # 3) seed policy docs if empty
        conn.execute(text("""
        INSERT INTO document (title, content, is_system)
        SELECT '이용약관',
'본 서비스는 교육 목적의 위키입니다. 사용자는 다음을 준수합니다.
1) 타인의 권리를 침해하지 않습니다.
2) 법령과 학교 규정을 준수합니다.
3) 관리자가 판단한 경우 문서를 수정/삭제할 수 있습니다.',
               TRUE
        ON CONFLICT (title) DO NOTHING;
        """))
        conn.execute(text("""
        INSERT INTO document (title, content, is_system)
        SELECT '개인정보처리방침',
'수집 항목: 학교 이메일, 비밀번호(해시), 로그인/문서 활동 로그
이용 목적: 사용자 인증, 서비스 운영 기록 관리
보관/파기: 탈퇴 즉시 정보 삭제, 로그는 보관 후 파기
제3자 제공/국외이전: 하지 않음
정보주체 권리: 열람/정정/삭제/처리정지 요청 및 동의 철회 가능
보호 조치: 비밀번호는 평문이 아닌 해시로 저장, 최소 권한 원칙으로 접근 통제',
               TRUE
        ON CONFLICT (title) DO NOTHING;
        """))

# Run-once before first request
_ran = {"done": False}
@app.before_request
def _run_once():
    if not _ran["done"]:
        ensure_schema_and_seed()
        _ran["done"] = True

# ---------- Routes ----------
@app.get("/")
def home():
    docs = db.session.execute(
        db.select(Document).order_by(Document.updated_at.desc()).limit(5)
    ).scalars().all()
    quick = db.session.execute(
        db.select(Document).where(Document.title.in_(["이용약관","개인정보처리방침"]))
    ).scalars().all()
    return render_template("home.html", docs=docs, quick=quick)

@app.get("/docs")
def docs():
    docs = db.session.execute(
        db.select(Document).order_by(Document.title.asc())
    ).scalars().all()
    return render_template("docs.html", docs=docs)

@app.get("/docs/<path:title>")
def view_doc(title):
    doc = db.session.execute(
        db.select(Document).where(Document.title == title)
    ).scalar_one_or_none()
    if not doc:
        abort(404)
    return render_template("doc.html", doc=doc)

@app.route("/create", methods=["GET","POST"])
@login_required
def create():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        if not title:
            flash("제목을 입력하세요.", "error")
            return redirect(url_for("create"))
        doc = Document(title=title, content=content)
        db.session.add(doc)
        db.session.commit()
        return redirect(url_for("view_doc", title=title))
    return render_template("create.html")

@app.get("/signup")
def signup_form():
    tos = db.session.execute(
        db.select(Document).where(Document.title=="이용약관")
    ).scalar_one_or_none()
    priv = db.session.execute(
        db.select(Document).where(Document.title=="개인정보처리방침")
    ).scalar_one_or_none()
    return render_template("signup.html",
        tos_text=(tos.content if tos else ""),
        privacy_text=(priv.content if priv else ""))

@app.post("/signup")
def signup():
    email = request.form.get("email","").strip()
    pw = request.form.get("password","")
    agree_tos = request.form.get("agree_tos") == "on"
    agree_priv = request.form.get("agree_priv") == "on"

    if not agree_tos or not agree_priv:
        flash("이용약관과 개인정보처리방침에 동의해야 가입할 수 있습니다.", "error")
        return redirect(url_for("signup_form"))

    if not email or "@" not in email:
        flash("유효한 이메일을 입력하세요.", "error")
        return redirect(url_for("signup_form"))

    # 학교 이메일 제한 (원하면 해제 가능)
    if not email.endswith("@bl-m.kr"):
        flash("학교 이메일(@bl-m.kr)만 허용됩니다.", "error")
        return redirect(url_for("signup_form"))

    if db.session.execute(db.select(User).where(User.email==email)).scalar_one_or_none():
        flash("이미 가입된 이메일입니다.", "error")
        return redirect(url_for("login"))

    h = generate_password_hash(pw)
    user = User(email=email, pw_hash=h)
    db.session.add(user)
    db.session.commit()
    flash("가입이 완료되었습니다. 로그인하세요.", "success")
    return redirect(url_for("login"))

@app.get("/login")
def login():
    return render_template("login.html")

@app.post("/login")
def do_login():
    email = request.form.get("email","").strip()
    pw = request.form.get("password","")
    user = db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()

    if not user or not user.pw_hash or not check_password_hash(user.pw_hash, pw):
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
        return redirect(url_for("login"))
    session["uid"] = user.id
    return redirect(url_for("home"))

@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.post("/account/delete")
@login_required
def delete_account():
    u = db.session.get(User, session["uid"])
    db.session.delete(u)
    db.session.commit()
    session.clear()
    flash("계정이 삭제되었습니다.", "success")
    return redirect(url_for("home"))

@app.get("/logs")
@login_required
def logs():
    # simple placeholder log page
    return render_template("logs.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
