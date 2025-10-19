from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, UniqueConstraint
from werkzeug.security import generate_password_hash, check_password_hash
import os, datetime

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL","sqlite:///local.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY","byeollae123")

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    pw_hash = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    __table_args__ = (UniqueConstraint('title','is_system', name='uq_system_title'),)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

TERMS_DEFAULT = """1. 본 서비스는 교육 목적의 위키입니다.
2. 타인의 권리를 침해하지 않습니다.
3. 관련 법과 규정을 준수합니다.
4. 관리자가 필요하다고 판단하는 경우 문서를 수정/삭제할 수 있습니다.
"""
PRIVACY_DEFAULT = """수집 항목: 학교 이메일(@bl-m.kr), 비밀번호(해시), 로그인/문서 활동 로그
이용 목적: 사용자 인증 및 서비스 운영
보관 기간: 법령상 보관이 필요한 기간 동안 안전하게 보관 후 파기
제3자 제공 / 국외이전: 없음
보호 조치: 최소 권한 원칙, 암호화 저장, 접근 통제
"""

@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = User.query.get(uid)

def ensure_seed():
    db.create_all()
    def upsert(title, content):
        doc = Document.query.filter_by(title=title, is_system=True).first()
        if not doc:
            doc = Document(title=title, content=content, is_system=True)
            db.session.add(doc)
        else:
            if not doc.content:
                doc.content = content
        return doc
    upsert("이용약관", TERMS_DEFAULT)
    upsert("개인정보처리방침", PRIVACY_DEFAULT)
    db.session.commit()

@app.before_request
def _run_once():
    if not hasattr(app, "_seeded"):
        try:
            ensure_seed()
        finally:
            app._seeded = True

def log(action):
    try:
        db.session.add(ActivityLog(user_id=session.get("uid"), action=action))
        db.session.commit()
    except Exception:
        db.session.rollback()

@app.route("/")
def home():
    recent_docs = Document.query.filter_by(is_system=False).order_by(Document.updated_at.desc()).limit(5).all()
    return render_template("home.html", recent_docs=recent_docs)

@app.route("/login", methods=["GET","POST"])
def login():
    error=None
    if request.method=="POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not email.endswith("@bl-m.kr"):
            error="학교 이메일(@bl-m.kr)만 사용할 수 있습니다."
        else:
            user = User.query.filter(func.lower(User.email)==email).first()
            if user and check_password_hash(user.pw_hash, password):
                session["uid"] = user.id
                log("로그인")
                return redirect(url_for("home"))
            else:
                error="이메일 또는 비밀번호가 올바르지 않습니다."
    return render_template("login.html", error=error)

@app.route("/logout", methods=["POST"])
def logout():
    log("로그아웃")
    session.clear()
    return redirect(url_for("home"))

@app.route("/signup", methods=["GET","POST"])
def signup():
    error=None
    if request.method=="POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not email.endswith("@bl-m.kr"):
            error="학교 이메일(@bl-m.kr)만 가입할 수 있습니다."
        elif len(password)<4:
            error="비밀번호는 4자 이상이어야 합니다."
        else:
            try:
                if User.query.filter(func.lower(User.email)==email).first():
                    error="이미 가입된 이메일입니다."
                else:
                    u = User(email=email, pw_hash=generate_password_hash(password))
                    db.session.add(u)
                    db.session.commit()
                    session["uid"]=u.id
                    log("회원가입")
                    return redirect(url_for("home"))
            except Exception as e:
                db.session.rollback()
                error="회원가입 처리 중 오류가 발생했습니다."
    return render_template("signup.html", error=error)

@app.route("/withdraw")
def delete_account():
    if not g.user:
        return redirect(url_for('login'))
    try:
        uid = g.user.id
        ActivityLog.query.filter_by(user_id=uid).delete()
        db.session.delete(g.user)
        db.session.commit()
        session.clear()
        return redirect(url_for('home'))
    except Exception:
        db.session.rollback()
        return redirect(url_for('home'))

@app.route("/documents")
def list_documents():
    docs = Document.query.filter_by(is_system=False).order_by(Document.updated_at.desc()).all()
    return render_template("list.html", docs=docs)

@app.route("/document/<int:doc_id>")
def view_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return render_template("view.html", doc=doc)

@app.route("/document/create", methods=["GET","POST"])
def create_document():
    if not g.user:
        return redirect(url_for("login"))
    if request.method=="POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        if title:
            d = Document(title=title, content=content, is_system=False)
            db.session.add(d)
            db.session.commit()
            log(f"문서 생성: {title}")
            return redirect(url_for("view_document", doc_id=d.id))
    return render_template("edit.html", doc=None)

@app.route("/document/<int:doc_id>/edit", methods=["GET","POST"])
def edit_document(doc_id):
    if not g.user:
        return redirect(url_for("login"))
    doc = Document.query.get_or_404(doc_id)
    if request.method=="POST":
        doc.title = request.form.get("title","").strip() or doc.title
        doc.content = request.form.get("content","")
        db.session.commit()
        log(f"문서 편집: {doc.title}")
        return redirect(url_for("view_document", doc_id=doc.id))
    return render_template("edit.html", doc=doc)

@app.route("/logs")
def view_logs():
    if not g.user:
        return redirect(url_for("login"))
    logs = ActivityLog.query.filter_by(user_id=g.user.id).order_by(ActivityLog.created_at.desc()).limit(100).all()
    return render_template("logs.html", logs=logs)

@app.route("/policy/<slug>")
def policy(slug):
    if slug=="terms":
        doc = Document.query.filter_by(title="이용약관", is_system=True).first()
    else:
        doc = Document.query.filter_by(title="개인정보처리방침", is_system=True).first()
    return jsonify({"title": doc.title if doc else "", "content_html": (doc.content or "").replace("\\n","<br>")})

@app.route("/system/<slug>")
def view_system_doc(slug):
    if slug=="terms":
        doc = Document.query.filter_by(title="이용약관", is_system=True).first()
    else:
        doc = Document.query.filter_by(title="개인정보처리방침", is_system=True).first()
    return render_template("view.html", doc=doc)

if __name__ == "__main__":
    app.run(debug=True)
