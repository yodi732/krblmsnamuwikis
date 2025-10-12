
import os
from datetime import datetime, timedelta, date
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, current_user, login_required, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText

ALLOWED_DOMAIN = "@bl-m.kr"
MAX_LOGIN_FAILS_PER_DAY = 10

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL","sqlite:///app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SECRET_KEY","dev-secret")

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# --------------- Models ---------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    agreed_at = db.Column(db.DateTime, nullable=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class EmailVerificationToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)

class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(32), nullable=False)   # CREATE/UPDATE/DELETE/LOGIN_FAIL/LOGIN_OK etc
    document_id = db.Column(db.Integer, nullable=True)
    actor_email = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class LoginAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    day = db.Column(db.Date, nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --------------- Helpers ---------------
def send_email(to_addr, subject, html):
    host = os.getenv("SMTP_HOST")
    if not host:
        print("[WARN] SMTP is not configured; email to", to_addr, "subject:", subject)
        return
    port = int(os.getenv("SMTP_PORT","587"))
    user = os.getenv("SMTP_USER")
    pw = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("SMTP_FROM", user)
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        if user and pw:
            s.login(user, pw)
        s.sendmail(from_addr, [to_addr], msg.as_string())

def log(action, doc_id=None):
    db.session.add(Log(action=action, document_id=doc_id, actor_email=(current_user.email if current_user.is_authenticated else None)))
    db.session.commit()

def daily_fail_count(email):
    rec = LoginAttempt.query.filter_by(email=email, day=date.today()).first()
    return rec.count if rec else 0

def inc_fail(email):
    rec = LoginAttempt.query.filter_by(email=email, day=date.today()).first()
    if not rec:
        rec = LoginAttempt(email=email, day=date.today(), count=1)
        db.session.add(rec)
    else:
        rec.count += 1
    db.session.commit()

# --------------- Routes ---------------
@app.route("/")
def index():
    docs = Document.query.filter_by(parent_id=None).order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.route("/logs")
@login_required
def logs():
    logs = Log.query.order_by(Log.created_at.desc()).limit(100).all()
    return render_template("logs.html", logs=logs)

@app.route("/privacy")
def privacy():
    return render_template("privacy.html", today=datetime.utcnow().date())

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        agree = request.form.get("agree") == "on"
        if not email.endswith(ALLOWED_DOMAIN):
            flash("학교 이메일(@bl-m.kr)만 가입할 수 있습니다.", "error")
            return redirect(url_for("register"))
        if not agree:
            flash("약관 및 개인정보 처리방침에 동의해야 합니다.", "error")
            return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "error"); return redirect(url_for("register"))
        u = User(email=email, password=generate_password_hash(password), agreed_at=datetime.utcnow())
        db.session.add(u); db.session.commit()
        tok = EmailVerificationToken(user_id=u.id, token=uuid4().hex, expires_at=datetime.utcnow()+timedelta(hours=24))
        db.session.add(tok); db.session.commit()
        verify_link = url_for("verify_email", token=tok.token, _external=True)
        send_email(u.email, "[별내위키] 이메일 인증", f"<p>다음 링크를 클릭해 인증을 완료하세요:</p><p><a href='{verify_link}'>{verify_link}</a></p>")
        flash("가입이 완료되었습니다. 이메일로 전송된 인증 링크를 확인하세요.", "ok")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/verify")
def verify_email():
    token = request.args.get("token")
    t = EmailVerificationToken.query.filter_by(token=token).first()
    if not t or t.expires_at < datetime.utcnow():
        flash("인증 링크가 유효하지 않습니다.", "error")
        return redirect(url_for("login"))
    u = db.session.get(User, t.user_id)
    u.email_verified = True
    db.session.delete(t)
    db.session.commit()
    flash("이메일 인증이 완료되었습니다. 로그인 해 주세요.", "ok")
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if daily_fail_count(email) >= MAX_LOGIN_FAILS_PER_DAY:
            flash("로그인 실패 횟수를 초과했습니다. 내일 다시 시도하세요.", "error")
            return redirect(url_for("login"))
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            inc_fail(email); log("LOGIN_FAIL")
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return redirect(url_for("login"))
        if not user.email_verified:
            flash("이메일 인증 후 로그인할 수 있습니다.", "error")
            return redirect(url_for("login"))
        login_user(user)
        log("LOGIN_OK")
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/forgot", methods=["GET","POST"])
def forgot():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            tok = PasswordResetToken(user_id=user.id, token=uuid4().hex, expires_at=datetime.utcnow()+timedelta(hours=1))
            db.session.add(tok); db.session.commit()
            reset_link = url_for("reset_password", token=tok.token, _external=True)
            send_email(user.email, "[별내위키] 비밀번호 재설정", f"<p>아래 링크에서 비밀번호를 재설정하세요:</p><p><a href='{reset_link}'>{reset_link}</a></p>")
        flash("비밀번호 재설정 메일을(가능한 경우) 발송했습니다.", "ok")
        return redirect(url_for("login"))
    return render_template("forgot.html")

@app.route("/reset", methods=["GET","POST"])
def reset_password():
    token = request.args.get("token")
    t = PasswordResetToken.query.filter_by(token=token).first()
    if not t or t.expires_at < datetime.utcnow():
        flash("토큰이 유효하지 않습니다.", "error")
        return redirect(url_for("login"))
    if request.method == "POST":
        pw = request.form.get("password","")
        u = db.session.get(User, t.user_id)
        u.password = generate_password_hash(pw)
        db.session.delete(t); db.session.commit()
        flash("비밀번호가 변경되었습니다. 로그인하세요.", "ok")
        return redirect(url_for("login"))
    return render_template("reset.html")

# ---- Documents (only internal members) ----
def must_be_member():
    return current_user.is_authenticated and current_user.email.endswith(ALLOWED_DOMAIN) and current_user.email_verified

@app.route("/create", methods=["POST"])
def create():
    if not must_be_member():
        flash("학교 구성원만 문서를 만들 수 있습니다.", "error"); return redirect(url_for("index"))
    title = request.form.get("title","").strip()
    content = request.form.get("content","").strip()
    if not title:
        flash("제목을 입력하세요.", "error"); return redirect(url_for("index"))
    d = Document(title=title, content=content, author_id=current_user.id)
    db.session.add(d); db.session.commit()
    log("CREATE", d.id)
    return redirect(url_for("index"))

@app.route("/delete/<int:doc_id>", methods=["POST"])
def delete(doc_id):
    if not must_be_member(): flash("권한이 없습니다.", "error"); return redirect(url_for("index"))
    d = db.session.get(Document, doc_id)
    if d:
        db.session.delete(d); db.session.commit(); log("DELETE", doc_id)
    return redirect(url_for("index"))

# ---- Account ----
@app.route("/account")
@login_required
def account():
    return render_template("account.html")

@app.route("/account/delete", methods=["POST"])
@login_required
def account_delete():
    uid = current_user.id
    # 문서 작성자 익명화
    db.session.query(Document).filter_by(author_id=uid).update({Document.author_id: None})
    # 토큰, 로그 삭제(정책에 따라 최소한으로 보관 가능)
    db.session.query(EmailVerificationToken).filter_by(user_id=uid).delete()
    db.session.query(PasswordResetToken).filter_by(user_id=uid).delete()
    # 계정 삭제
    u = db.session.get(User, uid)
    logout_user()
    db.session.delete(u)
    db.session.commit()
    flash("회원탈퇴가 완료되었습니다.", "ok")
    return redirect(url_for("index"))

# --------------- CLI ---------------
@app.cli.command("init-db")
def init_db():
    """Create tables"""
    db.create_all()
    print("Tables created.")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
