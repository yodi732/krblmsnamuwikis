\
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///byeollae.db"
SECRET_KEY = os.getenv("SECRET_KEY") or "dev-secret"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = SECRET_KEY

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    pw_hash = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), unique=True, nullable=False)
    content = db.Column(db.Text, default="")
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = db.session.get(User, uid)

# ----- Schema & Seed once -----
_has_seeded = False
@app.before_request
def ensure_schema_and_seed():
    global _has_seeded
    if _has_seeded:
        return
    db.create_all()

    def upsert(title, content, is_system=True):
        d = Document.query.filter_by(title=title).first()
        if not d:
            d = Document(title=title, content=content, is_system=is_system)
            db.session.add(d)
        else:
            if is_system:
                d.is_system = True
            if not d.content:
                d.content = content

    terms = """본 서비스는 교육 목적의 위키입니다. 사용자는 다음을 준수합니다.
1) 타인의 권리를 침해하지 않습니다.
2) 법령과 학교 규정을 준수합니다.
3) 관리자가 판단한 경우 문서를 수정/삭제할 수 있습니다.
"""
    privacy = """개인정보처리방침(요약)
1. 수집 항목: 학교 이메일(@bl-m.kr), 비밀번호(해시), 로그인/문서 활동 로그
2. 이용 목적: 사용자 인증, 서비스 운영 기록 관리
3. 보관/파기: 탈퇴 즉시 정보 삭제, 로그는 법령상 보관 기간 보관 후 파기
4. 제3자 제공/국외이전: 하지 않음
5. 열람·정정·삭제·처리정지 요구 및 동의 철회 가능
6. 보호조치: 비밀번호는 해시로만 저장, 최소 권한 원칙으로 접근 통제
"""
    upsert("이용약관", terms, True)
    upsert("개인정보처리방침", privacy, True)
    db.session.commit()
    _has_seeded = True

# ----- Routes -----
@app.route("/")
def home():
    recent = Document.query.order_by(Document.updated_at.desc().nullslast()).limit(5).all()
    return render_template("index.html", recent=recent)

@app.route("/docs")
def docs():
    docs = Document.query.order_by(Document.title.asc()).all()
    return render_template("docs.html", docs=docs)

@app.route("/docs/<path:title>")
def view_doc(title):
    doc = Document.query.filter_by(title=title).first_or_404()
    return render_template("view.html", doc=doc)

@app.route("/create", methods=["GET", "POST"])
def create():
    if not g.user:
        return redirect(url_for("login"))
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        if not title:
            flash("제목은 필수입니다.")
            return redirect(url_for("create"))
        if Document.query.filter_by(title=title).first():
            flash("이미 존재하는 제목입니다.")
            return redirect(url_for("create"))
        d = Document(title=title, content=content, is_system=False)
        db.session.add(d)
        db.session.commit()
        return redirect(url_for("view_doc", title=title))
    return render_template("create.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        agree_terms = request.form.get("agree_terms")
        agree_privacy = request.form.get("agree_privacy")

        if not (agree_terms and agree_privacy):
            flash("약관과 개인정보처리방침에 모두 동의해야 가입할 수 있습니다.")
            return redirect(url_for("signup"))

        if not email.endswith("@bl-m.kr"):
            flash("학교 이메일(@bl-m.kr)만 가입할 수 있습니다.")
            return redirect(url_for("signup"))

        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.")
            return redirect(url_for("signup"))

        pw_hash = generate_password_hash(password)
        u = User(email=email, pw_hash=pw_hash)
        db.session.add(u)
        db.session.commit()
        session["uid"] = u.id
        return redirect(url_for("home"))
    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        pw = request.form.get("password","")
        user = User.query.filter_by(email=email).first()
        # NULL 가드 + 사용자 친화 메시지
        if (not user) or (not user.pw_hash) or (not check_password_hash(user.pw_hash, pw)):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.")
            return redirect(url_for("login"))
        session["uid"] = user.id
        return redirect(url_for("home"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/delete-account", methods=["POST"])
def delete_account():
    if not g.user:
        return ("Unauthorized", 401)
    # 계정 삭제 → 홈으로
    db.session.delete(g.user)
    db.session.commit()
    session.clear()
    return ("", 204)

# alias used by JS
delete_account.methods = ["POST"]
app.add_url_rule("/delete_account", view_func=delete_account, methods=["POST"])

@app.route("/logs")
def logs():
    if not g.user:
        return redirect(url_for("login"))
    # Placeholder logs
    return render_template("view.html", doc=type("obj",(object,),{"title":"로그", "content":"(여기에 운영 로그가 표시됩니다.)"})())

if __name__ == "__main__":
    app.run(debug=True)
