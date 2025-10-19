
from datetime import datetime
import os
from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///app.db").replace("postgres://","postgresql://")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)
    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    parent = db.relationship("Document", remote_side=[id], backref="children")
    def can_add_child(self):
        return self.parent_id is None

def current_user():
    uid = session.get("uid")
    return db.session.get(User, uid) if uid else None

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

TERMS_TITLE = "이용약관"
PRIV_TITLE = "개인정보처리방침"
TERMS_BODY = """본 서비스는 교육 목적의 위키입니다. 사용자는 다음을 준수합니다.
1) 타인의 권리를 침해하지 않습니다.
2) 법령과 학교 규정을 준수합니다.
3) 관리자가 판단할 경우 문서를 수정/삭제할 수 있습니다.
"""
PRIV_BODY = """본 위키는 서비스 제공을 위해 최소한의 개인정보만 수집·이용합니다.
1. 수집 항목: 학교 이메일(@bl-m.kr), 비밀번호(해시 처리), 로그인/문서 활동 로그
2. 이용 목적: 사용자 인증, 서비스 운영 기록 관리
3. 보관 및 파기: 회원 탈퇴 즉시 계정 정보는 삭제하며, 법령상 보관이 필요한 로그는 해당 기간 동안 안전하게 보관 후 파기합니다.
4. 제3자 제공/국외이전: 하지 않습니다.
5. 정보주체 권리: 열람·정정·삭제·처리정지 요구 및 동의 철회 가능
6. 보호 조치: 비밀번호는 평문이 아닌 해시로 저장하며, 최소 권한 원칙으로 접근을 통제합니다.
문의: lyhjs1115@gmail.com
"""
def ensure_seed_docs():
    terms = Document.query.filter_by(title=TERMS_TITLE).first()
    if not terms:
        db.session.add(Document(title=TERMS_TITLE, body=TERMS_BODY))
    privacy = Document.query.filter_by(title=PRIV_TITLE).first()
    if not privacy:
        db.session.add(Document(title=PRIV_TITLE, body=PRIV_BODY))
    db.session.commit()

@app.route("/")
def home():
    docs = Document.query.order_by(Document.title.asc()).all()
    return render_template("home.html", docs=docs, me=current_user())

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        pw = request.form.get("password","")
        if not email.endswith("@bl-m.kr"):
            flash("학교 이메일(@bl-m.kr)만 로그인할 수 있습니다.", "error")
            return render_template("login.html", me=current_user())
        user = User.query.filter(db.func.lower(User.email)==email.lower()).first()
        if not user or not user.check_password(pw):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return render_template("login.html", me=current_user())
        session["uid"] = user.id
        return redirect(request.args.get("next") or url_for("home"))
    return render_template("login.html", me=current_user())

@app.route("/logout")
def logout():
    session.pop("uid", None)
    return redirect(url_for("home"))

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        pw = request.form.get("password","")
        agree_terms = request.form.get("agree_terms") == "on"
        agree_priv = request.form.get("agree_priv") == "on"
        if not (agree_terms and agree_priv):
            flash("약관과 개인정보처리방침에 모두 동의해야 합니다.", "error")
            return render_template("signup.html", me=current_user())
        if not email.endswith("@bl-m.kr"):
            flash("학교 이메일(@bl-m.kr)만 회원가입할 수 있습니다.", "error")
            return render_template("signup.html", me=current_user())
        if User.query.filter(db.func.lower(User.email)==email.lower()).first():
            flash("이미 가입된 이메일입니다.", "error")
            return render_template("signup.html", me=current_user())
        user = User(email=email)
        user.set_password(pw)
        db.session.add(user); db.session.commit()
        session["uid"] = user.id
        return redirect(url_for("home"))
    return render_template("signup.html", me=current_user())

@app.route("/create", methods=["GET","POST"])
@login_required
def create():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        body = request.form.get("body","")
        parent_id = request.form.get("parent_id")
        parent = None
        if parent_id:
            parent = db.session.get(Document, int(parent_id))
            if parent and not parent.can_add_child():
                flash("하위문서의 하위문서는 만들 수 없습니다.", "error")
                return redirect(url_for("create"))
        doc = Document(title=title, body=body, parent=parent)
        db.session.add(doc); db.session.commit()
        return redirect(url_for("doc", doc_id=doc.id))
    parents = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
    return render_template("create.html", parents=parents, me=current_user())

@app.route("/doc/<int:doc_id>")
def doc(doc_id):
    d = db.session.get(Document, doc_id) or abort(404)
    return render_template("document.html", d=d, me=current_user())

@app.route("/terms")
def terms():
    d = Document.query.filter_by(title=TERMS_TITLE).first() or abort(404)
    return redirect(url_for("doc", doc_id=d.id))

@app.route("/privacy")
def privacy():
    d = Document.query.filter_by(title=PRIV_TITLE).first() or abort(404)
    return redirect(url_for("doc", doc_id=d.id))

@app.cli.command("init-db")
def init_db():
    db.create_all(); ensure_seed_docs(); print("Initialized.")

if __name__ == "__main__":
    with app.app_context():
        db.create_all(); ensure_seed_docs()
    app.run(debug=True, host="0.0.0.0", port=5000)
