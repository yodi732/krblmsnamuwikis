\
import os
import re
import smtplib
from datetime import datetime, timedelta, date
from urllib.parse import urljoin
from email.mime.text import MIMEText

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, current_user, login_required, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import func, ForeignKey
from sqlalchemy.orm import relationship

# ------------------ App & DB ------------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///app.db")
if DATABASE_URL.startswith("postgres://"):
    # Render-old format fix
    DATABASE_URL = DATABASE_URL.replace("postgres://","postgresql://",1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# ------------------ Models ------------------

class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    agreed_at = db.Column(db.DateTime, nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    # Rate limit
    failed_login_count = db.Column(db.Integer, default=0, nullable=False)
    last_failed_login = db.Column(db.Date, nullable=True)

    documents = relationship("Document", back_populates="author", cascade="all,delete-orphan", passive_deletes=True)

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    parent_id = db.Column(db.Integer, db.ForeignKey("document.id", ondelete="SET NULL"), nullable=True)
    children = relationship("Document", backref=db.backref("parent", remote_side=[id]))
    
    author_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    author = relationship("User", back_populates="documents")

    def can_delete(self, user: "User"):
        return user.is_authenticated and (user.is_admin or self.author_id == user.id)


class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(20), nullable=False)  # CREATE / UPDATE / DELETE / LOGIN / LOGOUT
    document_id = db.Column(db.Integer, nullable=True)
    email = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)


class Token(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    purpose = db.Column(db.String(20), nullable=False)  # verify / reset
    token = db.Column(db.String(128), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)

# ------------------ Utilities ------------------

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

EMAIL_DOMAIN = "@bl-m.kr"
LOGIN_MAX_FAILS_PER_DAY = 10

def send_email(to_email: str, subject: str, body: str):
    """Try SMTP from env; if not configured, log body to console."""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    from_addr = os.environ.get("SMTP_FROM", smtp_user or "no-reply@example.com")

    if smtp_host and smtp_user and smtp_pass:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_email
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(from_addr, [to_email], msg.as_string())
    else:
        app.logger.info("== 이메일(미전송/로깅)==\nTo: %s\nSubject: %s\n\n%s", to_email, subject, body)

def make_token(user_id: int, purpose: str) -> str:
    t = Token(user_id=user_id, purpose=purpose, token=generate_password_hash(f"{user_id}-{datetime.utcnow().isoformat()}"))
    db.session.add(t)
    db.session.commit()
    return t.token

def verify_token(raw: str, purpose: str) -> User | None:
    tok = db.session.query(Token).filter_by(token=raw, purpose=purpose, used=False).first()
    if not tok:
        return None
    # 24h validity
    if datetime.utcnow() - tok.created_at > timedelta(hours=24):
        return None
    user = db.session.get(User, tok.user_id)
    if not user:
        return None
    tok.used = True
    db.session.commit()
    return user

def log_action(action: str, email: str | None, document_id: int | None = None):
    db.session.add(Log(action=action, email=email, document_id=document_id))
    db.session.commit()

# ------------------ Routes ------------------

@app.get("/")
def index():
    documents = (
        db.session.query(Document)
        .filter(Document.parent_id == None)
        .order_by(Document.created_at.desc())
        .all()
    )
    return render_template("index.html", documents=documents)

@app.post("/documents")
@login_required
def create_document():
    title = request.form.get("title","").strip()
    content = request.form.get("content","").strip()
    parent_id = request.form.get("parent_id","").strip() or None
    parent_id = int(parent_id) if parent_id else None

    if not title or not content:
        flash("제목과 내용을 입력하세요.")
        return redirect(url_for("index"))

    doc = Document(title=title, content=content, parent_id=parent_id, author_id=current_user.id)
    db.session.add(doc)
    db.session.commit()
    log_action("CREATE", current_user.email, document_id=doc.id)
    flash("문서가 저장되었습니다.")
    return redirect(url_for("index"))

@app.post("/documents/<int:doc_id>/delete")
@login_required
def delete_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        abort(404)
    if not doc.can_delete(current_user):
        abort(403)
    db.session.delete(doc)
    db.session.commit()
    log_action("DELETE", current_user.email, document_id=doc_id)
    flash("삭제되었습니다.")
    return redirect(url_for("index"))

@app.get("/login")
def login():
    return render_template("login.html")

@app.post("/login")
def post_login():
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    user = db.session.query(User).filter_by(email=email).first()

    # Fail counter per day
    if user:
        today = date.today()
        if user.last_failed_login == today and user.failed_login_count >= LOGIN_MAX_FAILS_PER_DAY:
            flash("로그인 시도 횟수가 초과되었습니다. 내일 다시 시도하세요.")
            return redirect(url_for("login"))

    if not user or not user.check_password(password):
        if user:
            today = date.today()
            if user.last_failed_login != today:
                user.last_failed_login = today
                user.failed_login_count = 0
            user.failed_login_count += 1
            db.session.commit()
        flash("이메일 또는 비밀번호가 올바르지 않습니다.")
        return redirect(url_for("login"))

    if not user.email_verified:
        flash("이메일 인증이 완료되지 않았습니다. 인증 메일을 다시 보내드렸습니다.")
        token = make_token(user.id, "verify")
        link = urljoin(request.host_url, url_for("verify_email", token=token))
        send_email(user.email, "[별내위키] 이메일 인증", f"아래 링크를 눌러 인증을 완료하세요:\n{link}\n24시간 유효")
        return redirect(url_for("login"))

    # success
    user.failed_login_count = 0
    user.last_failed_login = None
    db.session.commit()

    login_user(user)
    log_action("LOGIN", user.email)
    return redirect(url_for("index"))

@app.get("/logout")
@login_required
def logout():
    email = current_user.email
    logout_user()
    log_action("LOGOUT", email)
    flash("로그아웃 되었습니다.")
    return redirect(url_for("index"))

@app.get("/register")
def register():
    return render_template("register.html")

def valid_school_email(email: str) -> bool:
    return email.lower().endswith(EMAIL_DOMAIN)

@app.post("/register")
def post_register():
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    agree = request.form.get("agree")

    if not valid_school_email(email):
        flash("학교 이메일(@bl-m.kr)만 가입 가능합니다.")
        return redirect(url_for("register"))
    if not agree:
        flash("약관에 동의해야 가입할 수 있습니다.")
        return redirect(url_for("register"))
    if db.session.query(User).filter_by(email=email).first():
        flash("이미 가입된 이메일입니다.")
        return redirect(url_for("register"))

    user = User(email=email, email_verified=False, agreed_at=datetime.utcnow())
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = make_token(user.id, "verify")
    link = urljoin(request.host_url, url_for("verify_email", token=token))
    send_email(email, "[별내위키] 이메일 인증", f"아래 링크를 눌러 인증을 완료하세요:\n{link}\n24시간 유효")

    flash("가입이 완료되었습니다. 이메일 인증 링크를 확인하세요.")
    return redirect(url_for("login"))

@app.get("/verify")
def verify_email():
    token = request.args.get("token","")
    user = verify_token(token, "verify")
    if not user:
        flash("토큰이 유효하지 않거나 만료되었습니다.")
        return redirect(url_for("login"))
    user.email_verified = True
    db.session.commit()
    flash("이메일 인증이 완료되었습니다. 로그인하세요.")
    return redirect(url_for("login"))

@app.get("/forgot")
def forgot():
    return render_template("forgot.html")

@app.post("/forgot")
def post_forgot():
    email = request.form.get("email","").strip().lower()
    user = db.session.query(User).filter_by(email=email).first()
    if not user:
        flash("가입된 이메일이 없습니다.")
        return redirect(url_for("forgot"))
    token = make_token(user.id, "reset")
    link = urljoin(request.host_url, url_for("reset_password", token=token))
    send_email(user.email, "[별내위키] 비밀번호 재설정", f"아래 링크에서 새 비밀번호를 설정하세요:\n{link}\n24시간 유효")
    flash("재설정 링크를 이메일로 보냈습니다.")
    return redirect(url_for("login"))

@app.get("/reset")
def reset_password():
    token = request.args.get("token","")
    # 검증은 POST에서 최종 처리
    return render_template("reset.html")

@app.post("/reset")
def post_reset_password():
    token = request.args.get("token","")
    password = request.form.get("password","")
    user = verify_token(token, "reset")
    if not user:
        flash("토큰이 유효하지 않거나 만료되었습니다.")
        return redirect(url_for("login"))
    user.set_password(password)
    db.session.commit()
    flash("비밀번호가 변경되었습니다. 로그인하세요.")
    return redirect(url_for("login"))

@app.get("/account")
@login_required
def account():
    return render_template("account.html")

@app.post("/account/delete")
@login_required
def account_delete():
    # 로그아웃 먼저
    email = current_user.email
    uid = current_user.id
    logout_user()
    # 유저 삭제 (문서는 ondelete=SET NULL로 작성자만 제거되어 익명화)
    u = db.session.get(User, uid)
    if u:
        db.session.delete(u)
        db.session.commit()
    log_action("DELETE_USER", email)
    flash("회원탈퇴가 완료되었습니다. 개인 정보는 삭제되었습니다.")
    return redirect(url_for("index"))

@app.get("/logs")
def logs():
    rows = db.session.query(Log).order_by(Log.created_at.desc()).limit(200).all()
    return render_template("logs.html", rows=rows)

@app.get("/privacy")
def privacy():
    return render_template("privacy.html", today=datetime.utcnow().strftime("%Y-%m-%d"))

@app.get("/terms")
def terms():
    return render_template("terms.html")

# --------------- CLI ---------------
@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("DB initialized.")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
