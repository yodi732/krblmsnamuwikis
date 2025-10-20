import os, sys, logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///local.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

app = Flask(__name__)
app.config.update(SQLALCHEMY_DATABASE_URI=DATABASE_URL, SQLALCHEMY_TRACK_MODIFICATIONS=False, SECRET_KEY=SECRET_KEY)

# ensure logs show up on Render
stream = logging.StreamHandler(sys.stdout)
stream.setLevel(logging.INFO)
app.logger.addHandler(stream)
app.logger.setLevel(logging.INFO)

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    pw_hash = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('title','is_system', name='uq_title_is_system'),)

def seed_terms():
    terms_text = """
    <h3>이용약관 (요약)</h3>
    <ol>
      <li>타인의 권리를 침해하지 않습니다.</li>
      <li>법령과 학교 규정을 준수합니다.</li>
      <li>관리자가 판단한 경우 문서를 수정/삭제할 수 있습니다.</li>
    </ol>"""
    privacy_text = """
    <h3>개인정보처리방침 (요약)</h3>
    <ol>
      <li>수집 항목: 학교 이메일(@bl-m.kr), 비밀번호 해시, 활동 로그</li>
      <li>이용 목적: 인증, 서비스 운영 기록</li>
      <li>보관/파기: 법령 보존기간 이후 파기</li>
      <li>권리: 열람·정정·삭제 요청 가능</li>
      <li>보호조치: 최소권한·접근통제</li>
    </ol>"""
    for title, content in (("이용약관", terms_text), ("개인정보처리방침", privacy_text)):
        doc = Document.query.filter_by(title=title, is_system=True).first()
        if not doc:
            doc = Document(title=title, content=content, is_system=True)
            db.session.add(doc)
    db.session.commit()

@app.before_request
def bootstrap_and_user():
    g.user = None
    if "uid" in session:
        g.user = db.session.get(User, session["uid"])
    try:
        db.create_all()
        seed_terms()
    except Exception as e:
        db.session.rollback()
        app.logger.exception("bootstrap failed")

@app.errorhandler(Exception)
def all_errors(e):
    app.logger.exception("unhandled")
    return ("Internal Server Error", 500)

@app.context_processor
def inject_ids():
    t = Document.query.filter_by(title="이용약관", is_system=True).first()
    p = Document.query.filter_by(title="개인정보처리방침", is_system=True).first()
    return dict(terms_id=t.id if t else 0, privacy_id=p.id if p else 0)

@app.get("/")
def home():
    recent = Document.query.order_by(Document.updated_at.desc()).limit(5).all()
    return render_template("home.html", title="별내위키", recent=recent)

@app.route("/signup", methods=["GET","POST"])
def signup():
    t = Document.query.filter_by(title="이용약관", is_system=True).first()
    p = Document.query.filter_by(title="개인정보처리방침", is_system=True).first()
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not email.endswith("@bl-m.kr"):
            flash("학교 이메일(@bl-m.kr)만 가입 가능합니다.")
            return redirect(url_for("signup"))
        if not (request.form.get("agree_terms") and request.form.get("agree_privacy")):
            flash("이용약관/개인정보처리방침 동의가 필요합니다.")
            return redirect(url_for("signup"))
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.")
            return redirect(url_for("login"))
        pw_hash = f"sha1::{hash(password)}"
        u = User(email=email, pw_hash=pw_hash)
        db.session.add(u); db.session.commit()
        session["uid"] = u.id
        flash("가입 완료!")
        return redirect(url_for("home"))
    return render_template("signup.html", title="회원가입",
        terms_content=t.content if t else "", privacy_content=p.content if p else "")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        u = User.query.filter_by(email=email).first()
        if not u or u.pw_hash != f"sha1::{hash(password)}":
            flash("이메일 또는 비밀번호가 올바르지 않습니다.")
            return redirect(url_for("login"))
        session["uid"] = u.id
        flash("로그인되었습니다.")
        return redirect(url_for("home"))
    return render_template("login.html", title="로그인")

@app.get("/logout")
def logout():
    session.pop("uid", None); flash("로그아웃되었습니다."); return redirect(url_for("home"))

@app.route("/withdraw")
def withdraw():
    if not g.user: 
        flash("로그인이 필요합니다."); 
        return redirect(url_for("login"))
    db.session.delete(g.user); db.session.commit(); session.pop("uid", None)
    flash("계정이 삭제되었습니다."); return redirect(url_for("home"))

@app.get("/docs")
def list_docs():
    docs = Document.query.order_by(Document.title.asc()).all()
    return render_template("list.html", title="문서 목록", docs=docs)

@app.route("/docs/new", methods=["GET","POST"])
def new_doc():
    if request.method == "POST":
        d = Document(title=request.form["title"].strip(), content=request.form.get("content",""))
        db.session.add(d); db.session.commit()
        return redirect(url_for("view_doc", doc_id=d.id))
    return render_template("edit.html", title="문서 만들기", doc=None)

@app.get("/docs/<int:doc_id>")
def view_doc(doc_id):
    d = db.session.get(Document, doc_id)
    if not d: return ("Not Found", 404)
    return render_template("view.html", title=d.title, doc=d)

@app.route("/docs/<int:doc_id>/edit", methods=["GET","POST"])
def edit_doc(doc_id):
    if not g.user: 
        flash("로그인이 필요합니다."); 
        return redirect(url_for("login"))
    d = db.session.get(Document, doc_id)
    if request.method == "POST":
        d.title = request.form["title"].strip()
        d.content = request.form.get("content","")
        d.updated_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for("view_doc", doc_id=d.id))
    return render_template("edit.html", title="문서 편집", doc=d)

@app.get("/logs")
def logs():
    if not g.user: 
        flash("로그인이 필요합니다."); 
        return redirect(url_for("login"))
    return render_template("logs.html", title="로그", logs="(샘플) 서버 로그는 Render 대시보드에서 확인하세요.")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT","5000")))
