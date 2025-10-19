
import os
import re
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

db_url = os.environ.get("DATABASE_URL", "sqlite:///app.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

ALLOWED_EMAIL_DOMAIN = "@bl-m.kr"

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    pw_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    parent = db.relationship("Document", remote_side=[id])

def ensure_columns():
    with db.engine.connect() as conn:
        try:
            conn.execute(text("""
                ALTER TABLE document
                  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE,
                  ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE;
            """))
        except Exception:
            pass
        try:
            conn.execute(text("""
                ALTER TABLE "user"
                  ADD COLUMN IF NOT EXISTS pw_hash VARCHAR(255) NOT NULL DEFAULT '';
            """))
            conn.execute(text("""ALTER TABLE "user" ALTER COLUMN pw_hash DROP DEFAULT;"""))
        except Exception:
            pass
        try:
            conn.execute(text("""CREATE INDEX IF NOT EXISTS ix_document_parent_id ON document(parent_id);"""))
            conn.execute(text("""CREATE INDEX IF NOT EXISTS ix_document_is_system ON document(is_system);"""))
        except Exception:
            pass

def seed_system_docs():
    TERMS = """별내위키 이용약관
1. 목적: 본 약관은 별내위키(이하 '서비스')의 이용에 관한 회원과 회사의 권리·의무 및 책임 사항을 규정합니다.
2. 계정: 학교 이메일(@bl-m.kr)로만 가입·로그인이 가능합니다.
3. 게시물: 이용자는 법령과 공서양속을 위반하는 내용을 게시할 수 없으며, 저작권 등 제3자의 권리를 침해하지 않아야 합니다.
4. 제한/중지: 서비스 안정성 또는 법령 준수를 위하여 필요한 경우 게시물의 열람 제한, 수정 제한, 서비스 중지 등이 있을 수 있습니다.
5. 면책: 불가항력 또는 회원의 귀책사유로 인한 손해에 대하여 서비스는 책임을 지지 않습니다.
6. 준거법: 대한민국 법령을 따릅니다.
"""
    PRIVACY = """개인정보처리방침
1. 수집항목: 필수 - 이메일(학교 도메인), 비밀번호 해시. 선택 - 없음.
2. 수집·이용목적: 회원 식별, 로그인, 접근권한 관리, 서비스 운영 기록 보관.
3. 보유·이용기간: 회원 탈퇴 즉시 파기(로그 기록은 최대 3개월 보관 후 파기).
4. 제3자 제공/처리위탁: 원칙적으로 하지 않으며, 법령 근거가 있는 경우에 한해 제공될 수 있습니다.
5. 파기절차: DB에서 즉시 삭제하며 백업본은 순차적으로 덮어쓰기/삭제됩니다.
6. 안전성확보조치: 비밀번호 해시 저장, TLS, 접근통제.
7. 이용자 권리: 열람·정정·삭제·처리정지 요구 및 동의철회. 문의: lyhjs1115@gmail.com
"""
    def upsert(title, content):
        if not Document.query.filter_by(is_system=True, title=title).first():
            db.session.add(Document(title=title, content=content, is_system=True))
            db.session.commit()
    upsert("이용약관", TERMS)
    upsert("개인정보처리방침", PRIVACY)

with app.app_context():
    db.create_all()
    ensure_columns()
    seed_system_docs()

def current_user():
    uid = session.get("uid")
    return User.query.get(uid) if uid else None

def login_required(view):
    from functools import wraps
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper

def only_domain(email: str) -> bool:
    return email.lower().endswith(ALLOWED_EMAIL_DOMAIN)

@app.route("/")
def home():
    roots = Document.query.order_by(Document.is_system.desc(), Document.title.asc()).all()
    root_nodes = [d for d in roots if d.parent_id is None]
    recents = Document.query.order_by(Document.updated_at.desc()).limit(10).all()
    return render_template("home.html", root_nodes=root_nodes, recents=recents, me=current_user())

@app.route("/doc/<int:doc_id>")
def view_doc(doc_id):
    d = Document.query.get_or_404(doc_id)
    parent = Document.query.get(d.parent_id) if d.parent_id else None
    children = Document.query.filter_by(parent_id=d.id).order_by(Document.title.asc()).all()
    return render_template("view.html", d=d, parent=parent, children=children, me=current_user())

@app.route("/create", methods=["GET","POST"])
@login_required
def create():
    parents = Document.query.order_by(Document.title.asc()).all()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        parent_id = request.form.get("parent_id") or None
        if parent_id == "": parent_id=None
        if not title:
            flash("제목을 입력하세요.", "error")
            return redirect(url_for("create"))
        doc = Document(title=title, content=content, parent_id=parent_id)
        db.session.add(doc); db.session.commit()
        return redirect(url_for("view_doc", doc_id=doc.id))
    return render_template("create.html", parents=parents, me=current_user())

@app.route("/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete_doc(doc_id):
    d = Document.query.get_or_404(doc_id)
    if d.is_system: abort(403)
    if Document.query.filter_by(parent_id=d.id).count():
        flash("하위 문서가 있어 삭제할 수 없습니다.", "error")
        return redirect(url_for("view_doc", doc_id=d.id))
    db.session.delete(d); db.session.commit()
    return redirect(url_for("home"))

@app.route("/logs")
@login_required
def logs():
    recents = Document.query.order_by(Document.updated_at.desc()).limit(50).all()
    return render_template("logs.html", recents=recents, me=current_user())

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not only_domain(email):
            flash("학교 이메일(@bl-m.kr)만 로그인할 수 있습니다.", "error")
            return redirect(url_for("login"))
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.pw_hash, password):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return redirect(url_for("login"))
        session["uid"] = user.id
        return redirect(request.args.get("next") or url_for("home"))
    terms = Document.query.filter_by(is_system=True, title="이용약관").first()
    privacy = Document.query.filter_by(is_system=True, title="개인정보처리방침").first()
    return render_template("login.html", terms=terms, privacy=privacy, me=current_user())

@app.route("/logout")
def logout():
    session.pop("uid", None)
    return redirect(url_for("home"))

@app.route("/signup", methods=["GET","POST"])
def signup():
    terms = Document.query.filter_by(is_system=True, title="이용약관").first()
    privacy = Document.query.filter_by(is_system=True, title="개인정보처리방침").first()
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        agree_terms = request.form.get("agree_terms") == "on"
        agree_privacy = request.form.get("agree_privacy") == "on"
        if not only_domain(email):
            flash("학교 이메일(@bl-m.kr)로만 가입할 수 있습니다.", "error"); return redirect(url_for("signup"))
        if not (agree_terms and agree_privacy):
            flash("약관 및 개인정보처리방침 동의가 필요합니다.", "error"); return redirect(url_for("signup"))
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "error"); return redirect(url_for("login"))
        user = User(email=email, pw_hash=generate_password_hash(password))
        db.session.add(user); db.session.commit()
        flash("가입 완료! 로그인해 주세요.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html", terms=terms, privacy=privacy, me=current_user())

@app.route("/withdraw", methods=["POST"])
def withdraw():
    me_id = session.pop("uid", None)
    if me_id:
        me = User.query.get(me_id)
        if me:
            db.session.delete(me); db.session.commit()
    return redirect(url_for("home"))

@app.route("/terms")
def terms():
    doc = Document.query.filter_by(is_system=True, title="이용약관").first_or_404()
    return redirect(url_for("view_doc", doc_id=doc.id))

@app.route("/privacy")
def privacy():
    doc = Document.query.filter_by(is_system=True, title="개인정보처리방침").first_or_404()
    return redirect(url_for("view_doc", doc_id=doc.id))

@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
