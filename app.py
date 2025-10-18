
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, ForeignKey
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Config
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "dev-secret")
db_url = os.environ.get("DATABASE_URL", "sqlite:///blmwiki.db")
# Render sometimes provides postgres:// - convert to postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    parent = relationship("Document", remote_side=[id])
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_system = db.Column(db.Boolean, default=False, nullable=False)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)
    detail = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db.session.get(User, uid)

def login_required():
    if not current_user():
        flash("로그인이 필요합니다.", "warning")
        return redirect(url_for("login", next=request.path))

# Create tables
with app.app_context():
    db.create_all()

# System documents (read-only)
TERMS_TITLE = "이용약관"
TERMS_TEXT = """\
본 서비스는 교육 목적의 위키입니다. 사용자는 다음을 준수합니다.
1) 타인의 권리를 침해하지 않습니다.
2) 법령과 학교 규정을 준수합니다.
3) 관리자가 판단할 경우 문서를 수정/삭제할 수 있습니다.
"""

PRIVACY_TITLE = "개인정보처리방침"
PRIVACY_TEXT = """\
본 위키는 서비스 제공을 위해 최소한의 개인정보만 수집·이용합니다.

1. 수집 항목: 학교 이메일(@bl-m.kr), 비밀번호(해시 처리), 로그인/문서 활동 로그
2. 이용 목적: 사용자 인증, 서비스 운영 기록 관리
3. 보관 및 파기: 회원 탈퇴 즉시 계정 정보는 삭제하며, 관계 법령상 보관이 필요한 로그는 해당 기간 동안 안전하게 보관 후 파기합니다.
4. 제3자 제공/국외이전: 하지 않습니다.
5. 정보주체 권리: 열람·정정·삭제·처리정지 요구 및 동의 철회 가능
6. 보호 조치: 비밀번호는 평문이 아닌 해시로 저장하며, 최소 권한 원칙으로 접근을 통제합니다.
문의: lyhjs1115@gmail.com
"""

def ensure_system_docs():
    # Create or update system docs but keep them read-only
    terms = Document.query.filter_by(is_system=True, title=TERMS_TITLE).first()
    if not terms:
        terms = Document(title=TERMS_TITLE, content=TERMS_TEXT, is_system=True)
        db.session.add(terms)
    else:
        terms.content = TERMS_TEXT
    privacy = Document.query.filter_by(is_system=True, title=PRIVACY_TITLE).first()
    if not privacy:
        privacy = Document(title=PRIVACY_TITLE, content=PRIVACY_TEXT, is_system=True)
        db.session.add(privacy)
    else:
        privacy.content = PRIVACY_TEXT
    db.session.commit()

with app.app_context():
    ensure_system_docs()

# Utils
def log(action, detail):
    u = current_user()
    db.session.add(Log(action=action, detail=detail, user_id=(u.id if u else None)))
    db.session.commit()

# Routes
@app.get("/")
def home():
    # top-level docs (parent is NULL), recent docs
    roots = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
    recents = Document.query.order_by(Document.updated_at.desc()).limit(20).all()
    return render_template("home.html", roots=roots, recents=recents, me=current_user())

@app.get("/healthz")
def healthz():
    return "ok"

@app.get("/doc/<int:doc_id>")
def view_doc(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    children = Document.query.filter_by(parent_id=doc.id).order_by(Document.title.asc()).all()
    return render_template("doc.html", doc=doc, children=children, me=current_user())

@app.route("/new", methods=["GET","POST"])
def new_doc():
    if not current_user():
        return login_required()
    parent_id = request.args.get("parent", type=int)
    parent = db.session.get(Document, parent_id) if parent_id else None
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if not title:
            flash("제목을 입력하세요.", "danger")
            return render_template("new.html", parent=parent, me=current_user())
        doc = Document(title=title, content=content, parent_id=(parent.id if parent else None))
        db.session.add(doc)
        db.session.commit()
        log("create", f"doc#{doc.id} {doc.title}")
        return redirect(url_for("view_doc", doc_id=doc.id))
    return render_template("new.html", parent=parent, me=current_user())

@app.route("/doc/<int:doc_id>/edit", methods=["GET","POST"])
def edit_doc(doc_id):
    if not current_user():
        return login_required()
    doc = db.session.get(Document, doc_id) or abort(404)
    if doc.is_system:
        flash("시스템 문서는 수정할 수 없습니다.", "warning")
        return redirect(url_for("view_doc", doc_id=doc.id))
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        pid = request.form.get("parent_id", type=int)
        if not title:
            flash("제목을 입력하세요.", "danger"); return render_template("edit.html", doc=doc, me=current_user(), all_parents=Document.query.all())
        # Prevent setting self as parent or creating loop
        if pid == doc.id:
            flash("상위 문서 설정이 올바르지 않습니다.", "danger")
        else:
            doc.title = title
            doc.content = content
            doc.parent_id = pid if pid else None
            db.session.commit()
            log("update", f"doc#{doc.id} {doc.title}")
            return redirect(url_for("view_doc", doc_id=doc.id))
    return render_template("edit.html", doc=doc, me=current_user(), all_parents=Document.query.all())

@app.post("/doc/<int:doc_id>/delete")
def delete_doc(doc_id):
    if not current_user():
        return login_required()
    doc = db.session.get(Document, doc_id) or abort(404)
    if doc.is_system:
        flash("시스템 문서는 삭제할 수 없습니다.", "warning")
        return redirect(url_for("view_doc", doc_id=doc.id))
    # cascade: reparent children to its parent
    children = Document.query.filter_by(parent_id=doc.id).all()
    for c in children:
        c.parent_id = doc.parent_id
    db.session.delete(doc)
    db.session.commit()
    log("delete", f"doc#{doc.id} {doc.title}")
    flash("삭제되었습니다.", "success")
    return redirect(url_for("home"))

# Auth
ALLOWED_DOMAIN = "@bl-m.kr"

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        agree_terms = request.form.get("agree_terms") == "on"
        agree_privacy = request.form.get("agree_privacy") == "on"
        if not email or not pw:
            flash("이메일과 비밀번호를 입력하세요.", "danger")
        elif ALLOWED_DOMAIN and not email.endswith(ALLOWED_DOMAIN):
            flash(f"학교 이메일({ALLOWED_DOMAIN})만 가입할 수 있습니다.", "danger")
        elif not agree_terms or not agree_privacy:
            flash("약관과 개인정보처리방침에 동의해야 가입이 가능합니다.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "danger")
        else:
            u = User(email=email, password_hash=generate_password_hash(pw))
            db.session.add(u); db.session.commit()
            session["uid"] = u.id
            log("register", email)
            return redirect(url_for("home"))
    return render_template("register.html", domain=ALLOWED_DOMAIN, me=current_user())

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        u = User.query.filter_by(email=email).first()
        if not u or not check_password_hash(u.password_hash, pw):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "danger")
        else:
            session["uid"] = u.id
            log("login", email)
            nxt = request.args.get("next") or url_for("home")
            return redirect(nxt)
    return render_template("login.html", me=current_user())

@app.get("/logout")
def logout():
    if current_user():
        log("logout", current_user().email)
    session.pop("uid", None)
    return redirect(url_for("home"))

@app.route("/withdraw", methods=["GET","POST"])
def withdraw():
    if not current_user():
        return login_required()
    if request.method == "POST":
        u = current_user()
        email = u.email
        # delete user; keep logs as record (user_id can remain or be nulled if needed)
        session.pop("uid", None)
        db.session.delete(u); db.session.commit()
        log("withdraw", email)
        flash("회원 탈퇴가 완료되었습니다.", "success")
        return redirect(url_for("home"))
    return render_template("withdraw.html", me=current_user())

# Logs
@app.get("/logs")
def logs():
    if not current_user():
        return login_required()
    items = Log.query.order_by(Log.created_at.desc()).limit(200).all()
    return render_template("logs.html", items=items, me=current_user())

# Error page
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, msg="페이지를 찾을 수 없습니다.", me=current_user()), 404

# Run local
if __name__ == "__main__":
    app.run(debug=True, port=5000)
