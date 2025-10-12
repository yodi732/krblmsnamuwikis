

import os
from datetime import datetime, timedelta, date
from uuid import uuid4

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. postgresql://user:pass@host:port/dbname
SECRET_KEY = os.getenv("SECRET_KEY", "dev-"+str(uuid4()))

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
if DATABASE_URL:
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///local.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# ----- Models -----
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    agreed_at = db.Column(db.DateTime, nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # login rate limit per day
    fail_count = db.Column(db.Integer, default=0, nullable=False)
    fail_date = db.Column(db.Date, nullable=True)

    verify_token = db.Column(db.String(255), nullable=True)
    verify_expires = db.Column(db.DateTime, nullable=True)

    reset_token = db.Column(db.String(255), nullable=True)
    reset_expires = db.Column(db.DateTime, nullable=True)

    documents = db.relationship("Document", back_populates="author")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    parent = db.relationship("Document", remote_side=[id], backref="children")

    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    author = db.relationship("User", back_populates="documents")

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    document = db.relationship("Document")
    user_email = db.Column(db.String(255), nullable=True)  # show email instead of IP


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# util
def send_email(to_email, subject, body):
    # simple stdout "mailer" for Render logs; replaceable with SMTP later
    print(f"[MAIL] To: {to_email}\n[MAIL] Subject: {subject}\n[MAIL] Body:\n{body}\n")
    # TODO: integrate SMTP by env (MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD) if provided.

def require_school_email(email: str) -> bool:
    return email.lower().endswith("@bl-m.kr")

def daily_limit_exceeded(user: User) -> bool:
    today = date.today()
    if user.fail_date != today:
        user.fail_date = today
        user.fail_count = 0
        db.session.commit()
    return user.fail_count >= 10

def record_fail(user: User):
    today = date.today()
    if user.fail_date != today:
        user.fail_date = today
        user.fail_count = 0
    user.fail_count += 1
    db.session.commit()

# ----- Routes -----
@app.route("/")
def index():
    parents = (Document.query
               .filter_by(parent_id=None)
               .order_by(Document.created_at.desc())
               .all())
    children = (Document.query
                .filter(Document.parent_id.isnot(None))
                .order_by(Document.created_at.desc())
                .all())
    children_map = {}
    for c in children:
        children_map.setdefault(c.parent_id, []).append(c)
    return render_template("index.html", parents=parents, children_map=children_map)

@app.route("/doc/<int:doc_id>")
def view_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return render_template("document_view.html", doc=doc)

@app.route("/create", methods=["GET", "POST"])
def create_document():
    if not current_user.is_authenticated:
        flash("로그인 후 이용하세요.")
        return redirect(url_for("login"))
    if not current_user.email_verified:
        flash("이메일 인증 후 이용하세요.")
        return redirect(url_for("index"))
    parents = Document.query.filter_by(parent_id=None).order_by(Document.created_at.desc()).all()
    parent_id = request.args.get("parent_id", type=int)
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        parent_id = request.form.get("parent_id") or None
        if parent_id:
            # prevent third level nesting
            parent = Document.query.get(int(parent_id))
            if parent and parent.parent_id is not None:
                flash("하위 문서의 하위 문서는 만들 수 없습니다.")
                return redirect(url_for("create_document"))
        if not title:
            flash("제목을 입력하세요.")
            return redirect(url_for("create_document"))
        doc = Document(title=title, content=content or None, parent_id=(int(parent_id) if parent_id else None), author_id=current_user.id)
        db.session.add(doc)
        db.session.flush()
        db.session.add(Log(action="문서 생성", document_id=doc.id, user_email=current_user.email))
        db.session.commit()
        flash("문서를 만들었습니다.")
        return redirect(url_for("view_document", doc_id=doc.id))
    return render_template("document_form.html", doc=None, parents=parents, parent_id=parent_id)

@app.route("/edit/<int:doc_id>", methods=["GET","POST"])
def edit_document(doc_id):
    if not current_user.is_authenticated:
        flash("로그인 후 이용하세요.")
        return redirect(url_for("login"))
    if not current_user.email_verified:
        flash("이메일 인증 후 이용하세요.")
        return redirect(url_for("index"))
    doc = Document.query.get_or_404(doc_id)
    parents = Document.query.filter_by(parent_id=None).order_by(Document.created_at.desc()).all()
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        parent_id = request.form.get("parent_id") or None
        if parent_id:
            parent = Document.query.get(int(parent_id))
            if parent and parent.parent_id is not None:
                flash("하위 문서의 하위 문서는 만들 수 없습니다.")
                return redirect(url_for("edit_document", doc_id=doc.id))
        doc.title = title or doc.title
        doc.content = content or None
        doc.parent_id = int(parent_id) if parent_id else None
        db.session.add(Log(action="문서 수정", document_id=doc.id, user_email=current_user.email))
        db.session.commit()
        flash("수정되었습니다.")
        return redirect(url_for("view_document", doc_id=doc.id))
    return render_template("document_form.html", doc=doc, parents=parents)

@app.post("/delete/<int:doc_id>")
def delete_document(doc_id):
    if not current_user.is_authenticated or not current_user.email_verified:
        abort(403)
    doc = Document.query.get_or_404(doc_id)
    # delete children first (only one level deep exists by rule)
    for c in list(doc.children):
        db.session.delete(c)
    db.session.add(Log(action="문서 삭제", document_id=doc.id, user_email=current_user.email))
    db.session.delete(doc)
    db.session.commit()
    flash("삭제했습니다.")
    return redirect(url_for("index"))

@app.route("/logs")
def view_logs():
    logs = Log.query.order_by(Log.created_at.desc()).limit(200).all()
    return render_template("logs.html", logs=logs)

# ---- Auth ----
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        agree = request.form.get("agree")
        if not require_school_email(email):
            flash("학교 이메일(@bl-m.kr)만 가입 가능합니다.")
            return redirect(url_for("register"))
        if not agree:
            flash("약관과 방침에 동의해야 합니다.")
            return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.")
            return redirect(url_for("register"))
        u = User(email=email, agreed_at=datetime.utcnow())
        u.set_password(password)
        # email verify token
        token = uuid4().hex
        u.verify_token = token
        u.verify_expires = datetime.utcnow() + timedelta(hours=24)
        db.session.add(u)
        db.session.commit()
        link = url_for("verify_email", token=token, _external=True)
        send_email(email, "[별내위키] 이메일 인증", f"다음 링크를 24시간 내에 클릭하여 인증하세요:\n{link}")
        flash("가입 완료! 받은편지함의 인증 메일을 확인하세요.")
        return redirect(url_for("login"))
    return render_template("auth.html", mode="register")

@app.route("/verify/<token>")
def verify_email(token):
    u = User.query.filter_by(verify_token=token).first()
    if not u:
        flash("유효하지 않은 토큰입니다.")
        return redirect(url_for("index"))
    if u.verify_expires and u.verify_expires < datetime.utcnow():
        flash("토큰이 만료되었습니다. 로그인 후 인증 메일을 다시 요청하세요.")
        return redirect(url_for("login"))
    u.email_verified = True
    u.verify_token = None
    u.verify_expires = None
    db.session.commit()
    flash("이메일 인증이 완료되었습니다.")
    return redirect(url_for("index"))

@app.route("/resend")
@login_required
def resend_verification():
    if current_user.email_verified:
        flash("이미 인증된 계정입니다.")
        return redirect(url_for("index"))
    token = uuid4().hex
    current_user.verify_token = token
    current_user.verify_expires = datetime.utcnow() + timedelta(hours=24)
    db.session.commit()
    link = url_for("verify_email", token=token, _external=True)
    send_email(current_user.email, "[별내위키] 인증 메일 재발송", f"아래 링크로 인증을 완료하세요:\n{link}")
    flash("인증 메일을 다시 보냈습니다.")
    return redirect(url_for("index"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user:
            if daily_limit_exceeded(user):
                flash("로그인 실패가 하루 10회를 초과했습니다. 내일 다시 시도하세요.")
                return redirect(url_for("login"))
            if user.check_password(password):
                login_user(user)
                # reset fail counter on success
                user.fail_count = 0
                user.fail_date = date.today()
                db.session.commit()
                return redirect(url_for("index"))
            else:
                record_fail(user)
        flash("이메일 또는 비밀번호가 올바르지 않습니다.")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/forgot", methods=["GET","POST"])
def forgot():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = uuid4().hex
            user.reset_token = token
            user.reset_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            link = url_for("reset_with_token", token=token, _external=True)
            send_email(email, "[별내위키] 비밀번호 재설정", f"아래 링크로 1시간 내에 재설정하세요:\n{link}")
        flash("재설정 링크를 이메일로 보냈습니다(계정이 존재한다면).")
        return redirect(url_for("login"))
    return render_template("auth.html", mode="forgot")

@app.route("/reset/<token>", methods=["GET","POST"])
def reset_with_token(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or (user.reset_expires and user.reset_expires < datetime.utcnow()):
        flash("유효하지 않거나 만료된 링크입니다.")
        return redirect(url_for("login"))
    if request.method == "POST":
        pw = request.form.get("password") or ""
        user.set_password(pw)
        user.reset_token = None
        user.reset_expires = None
        db.session.commit()
        flash("비밀번호가 재설정되었습니다. 로그인하세요.")
        return redirect(url_for("login"))
    return """
    <form method='post' style='max-width:480px;margin:24px auto;font-family:system-ui'>
      <h3>새 비밀번호 설정</h3>
      <input name='password' type='password' required minlength='8' style='width:100%;padding:8px;border:1px solid #ddd;border-radius:8px'>
      <div style='margin-top:12px'><button>저장</button></div>
    </form>
    """

@app.route("/account")
@login_required
def account():
    return render_template("account.html")

@app.post("/account/delete")
@login_required
def delete_account():
    user = current_user
    # detach authored docs
    Document.query.filter_by(author_id=user.id).update({Document.author_id: None})
    # remove user
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash("회원탈퇴가 완료되었습니다. 개인정보가 삭제되었습니다.")
    return redirect(url_for("index"))

# static pages
@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

# convenience aliases for URLs in templates
@app.context_processor
def inject_urls():
    return dict(
        create_document_url=url_for("create_document"),
    )

# ----- DB init -----
with app.app_context():
    db.create_all()

# alias for template urls
create_document = create_document

if __name__ == "__main__":
    app.run(debug=True)
