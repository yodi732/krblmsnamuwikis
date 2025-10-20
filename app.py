import os
from datetime import datetime
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

def _normalized_db_uri(raw: str) -> str:
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql+psycopg://", 1)
    elif raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

    db_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = _normalized_db_uri(db_url)
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    from models import User, Document  # noqa

    app._schema_seed_done = False

    @app.before_request
    def _run_once():
        if getattr(app, "_schema_seed_done", False):
            return
        with app.app_context():
            ensure_schema_and_seed()
            app._schema_seed_done = True

    @app.get("/")
    def home():
        docs = Document.query.order_by(Document.created_at.desc()).limit(20).all()
        return render_template("index.html", docs=docs)

    @app.get("/docs")
    def docs_list():
        roots = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
        return render_template("docs.html", roots=roots)

    @app.get("/docs/<int:doc_id>")
    def doc_view(doc_id: int):
        doc = Document.query.get_or_404(doc_id)
        children = Document.query.filter_by(parent_id=doc.id).order_by(Document.title.asc()).all()
        return render_template("doc_view.html", doc=doc, children=children)

    @app.get("/login")
    def login_form():
        return render_template("login.html")

    @app.post("/login")
    def login():
        email = request.form.get("email", "").strip()
        pw = request.form.get("password", "").strip()

        row = db.session.execute(text('SELECT id, email, password_hash FROM "user" WHERE email=:e LIMIT 1'),
                                 {"e": email}).mappings().first()

        if not row or not row["password_hash"] or not check_password_hash(row["password_hash"], pw):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return redirect(url_for("login_form"))

        session["uid"] = row["id"]
        flash("로그인되었습니다.", "ok")
        return redirect(url_for("home"))

    @app.get("/logout")
    def logout():
        session.clear()
        flash("로그아웃되었습니다.", "ok")
        return redirect(url_for("home"))

    @app.get("/signup")
    def signup_form():
        return render_template("signup.html")

    @app.post("/signup")
    def signup():
        email = request.form.get("email", "").strip()
        pw = request.form.get("password", "").strip()
        agree_tos = request.form.get("agree_tos") == "on"
        agree_priv = request.form.get("agree_priv") == "on"

        if not email.endswith("@bl-m.kr"):
            flash("bl-m.kr 이메일만 가입할 수 있습니다.", "error")
            return redirect(url_for("signup_form"))

        if not agree_tos or not agree_priv:
            flash("이용약관과 개인정보처리방침에 동의해야 가입할 수 있습니다.", "error")
            return redirect(url_for("signup_form"))

        if len(pw) < 4:
            flash("비밀번호는 4자 이상 입력하세요.", "error")
            return redirect(url_for("signup_form"))

        exists = db.session.execute(text('SELECT 1 FROM "user" WHERE email=:e LIMIT 1'), {"e": email}).first()
        if exists:
            flash("이미 가입된 이메일입니다.", "error")
            return redirect(url_for("signup_form"))

        pw_hash = generate_password_hash(pw)
        db.session.execute(text(
            'INSERT INTO "user" (email, password_hash, created_at, is_admin) '
            'VALUES (:e, :h, :now, :adm)'
        ), {"e": email, "h": pw_hash, "now": datetime.utcnow(), "adm": False})
        db.session.commit()

        flash("회원가입 완료. 로그인 해주세요.", "ok")
        return redirect(url_for("login_form"))

    return app


def ensure_schema_and_seed():
    db.session.execute(text(r"""
    CREATE TABLE IF NOT EXISTS "user" (
        id SERIAL PRIMARY KEY,
        email VARCHAR UNIQUE NOT NULL,
        password_hash VARCHAR NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        is_admin BOOLEAN NOT NULL DEFAULT FALSE
    );
    """))

    db.session.execute(text(r"""
    CREATE TABLE IF NOT EXISTS document (
        id SERIAL PRIMARY KEY,
        title VARCHAR NOT NULL,
        content TEXT NOT NULL,
        is_system BOOLEAN NOT NULL DEFAULT FALSE,
        parent_id INTEGER REFERENCES document(id) ON DELETE SET NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    """))

    db.session.execute(text(r"""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_document_title ON document (title);
    """))

    db.session.execute(text(r"""
    INSERT INTO document (title, content, is_system)
    VALUES
    ('이용약관',
    '본 서비스는 교육 목적의 위키입니다. 사용자는 다음을 준수합니다.
1) 타인의 권리를 침해하지 않습니다.
2) 법령과 학교 규정을 준수합니다.
3) 관리자가 판단한 경우 문서를 수정/삭제할 수 있습니다.',
     TRUE)
    ON CONFLICT (title) DO NOTHING;
    """))

    db.session.execute(text(r"""
    INSERT INTO document (title, content, is_system)
    VALUES
    ('개인정보처리방침',
    '개인정보처리방침(요약)
1. 수집 항목: 학교 이메일, 비밀번호(해시), 로그인/문서 활동 로그
2. 이용 목적: 사용자 인증, 서비스 운영 기록 관리
3. 보관/파기: 탈퇴 즉시 정보 삭제, 법령상 보관 로그는 기간 보관 후 파기
4. 제3자 제공/국외 이전: 하지 않음
5. 정보주체 권리: 열람·정정·삭제·처리정지 요구 가능
6. 보호 조치: 최소 권한 접근 통제 및 해시 저장',
     TRUE)
    ON CONFLICT (title) DO NOTHING;
    """))

    db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
