
from flask import Flask, render_template, request, redirect, url_for, session, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
import os, datetime

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL or "sqlite:///local.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "byeollae-secret")

db = SQLAlchemy(app)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    parent = db.relationship("Document", remote_side=[id], backref="children")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    pw_hash = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)

def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db.session.get(User, uid)

TERMS = """본 서비스는 교육 목적의 위키입니다. 사용자는 다음을 준수합니다.
1) 타인의 권리를 침해하지 않습니다.
2) 법령과 학교 규정을 준수합니다.
3) 관리자가 판단할 경우 문서를 수정/삭제할 수 있습니다.
"""

PRIVACY = """개인정보처리방침 (요약)
1. 수집 항목: 학교 이메일(@bl-m.kr), 비밀번호(해시 처리), 로그인/문서 활동 로그
2. 이용 목적: 사용자 인증, 서비스 운영 기록 관리
3. 보관 및 파기: 회원 탈퇴 즉시 정보를 삭제하며, 법령상 보관이 필요한 로그는 해당 기간 보관 후 파기합니다.
4. 제3자 제공/국외이전: 하지 않습니다.
5. 정보주체 권리: 열람·정정·삭제·처리정지 요구 및 동의 철회 가능
6. 보호 조치: 비밀번호는 평문이 아닌 해시로 저장하며, 최소 권한 원칙으로 접근을 통제합니다.
"""

_seed_done = False

def seed_policies():
    def get_or_create(title, content):
        q = db.session.query(Document).filter(Document.title==title, Document.is_system.is_(True)).order_by(Document.id.asc())
        docs = q.all()
        if docs:
            for i, d in enumerate(docs):
                if i == 0:
                    d.content = content
                else:
                    db.session.delete(d)
            db.session.commit()
            return docs[0]
        doc = Document(title=title, content=content, is_system=True)
        db.session.add(doc)
        db.session.commit()
        return doc

    get_or_create("이용약관", TERMS)
    get_or_create("개인정보처리방침", PRIVACY)

def enforce_parent_rule(title, parent_id):
    if not parent_id:
        return True, None
    parent = db.session.get(Document, int(parent_id))
    if not parent:
        return False, "상위 문서를 찾을 수 없습니다."
    if parent.parent_id is not None:
        return False, "하위문서의 하위문서는 만들 수 없습니다."
    if title in ("이용약관", "개인정보처리방침"):
        return False, "해당 제목은 시스템 문서로만 사용됩니다."
    return True, None

@app.before_request
def _run_once():
    global _seed_done
    g.me = current_user()
    if not _seed_done:
        db.create_all()
        seed_policies()
        _seed_done = True

@app.route("/")
def home():
    recent = db.session.query(Document).order_by(Document.updated_at.desc().nullslast()).limit(10).all()
    return render_template("home.html", recent_docs=recent, me=g.me)

@app.route("/docs")
def list_docs():
    items = db.session.query(Document).order_by(Document.title.asc()).all()
    return render_template("list.html", items=items, me=g.me)

@app.route("/doc/<int:doc_id>")
def view_doc(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        return ("문서를 찾을 수 없습니다.", 404)
    return render_template("doc_view.html", doc=doc, me=g.me)

@app.route("/d/<path:title>")
def view_doc_by_title(title):
    doc = db.session.query(Document).filter(Document.title==title).order_by(Document.is_system.desc(), Document.id.asc()).first()
    if not doc:
        return ("문서를 찾을 수 없습니다.", 404)
    return render_template("doc_view.html", doc=doc, me=g.me)

@app.route("/create", methods=["GET","POST"])
def create():
    if not g.me:
        return redirect(url_for("login"))
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        parent_id = request.form.get("parent_id") or None
        ok, err = enforce_parent_rule(title, parent_id)
        if not ok:
            parents = db.session.query(Document).filter(Document.parent_id.is_(None)).order_by(Document.title.asc()).all()
            return render_template("create.html", error=err, parents=parents, me=g.me)
        doc = Document(title=title, content=content, parent_id=int(parent_id) if parent_id else None)
        db.session.add(doc)
        db.session.commit()
        return redirect(url_for("view_doc", doc_id=doc.id))
    parents = db.session.query(Document).filter(Document.parent_id.is_(None)).order_by(Document.title.asc()).all()
    return render_template("create.html", parents=parents, me=g.me)

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        pw = request.form.get("password","")
        if not email.endswith("@bl-m.kr"):
            error = "학교 이메일(@bl-m.kr)만 로그인할 수 있습니다."
        else:
            user = db.session.query(User).filter(User.email==email).first()
            if not user or not check_password_hash(user.pw_hash, pw):
                error = "이메일 또는 비밀번호가 올바르지 않습니다."
            else:
                session["uid"] = user.id
                return redirect(url_for("home"))
    return render_template("login.html", error=error, me=g.me)

@app.route("/signup", methods=["GET","POST"])
def signup():
    error=None
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        pw = request.form.get("password","")
        if not email.endswith("@bl-m.kr"):
            error = "학교 이메일(@bl-m.kr)만 가입할 수 있습니다."
        elif db.session.query(User).filter(User.email==email).first():
            error = "이미 가입된 이메일입니다."
        else:
            u = User(email=email, pw_hash=generate_password_hash(pw))
            db.session.add(u)
            db.session.commit()
            session["uid"] = u.id
            return redirect(url_for("home"))
    return render_template("signup.html", error=error, me=g.me)

@app.route("/logout")
def logout():
    session.pop("uid", None)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
