
import os, smtplib
from email.message import EmailMessage
from datetime import datetime
from urllib.parse import urljoin
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash

def _db_url():
    url = os.getenv("DATABASE_URL", "sqlite:///app.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY","dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    agreed_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    target = db.Column(db.String(255), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- mail ---
def serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="email-confirm")

def app_base():
    return os.getenv("APP_BASE_URL", request.url_root.rstrip("/"))

def send_mail(to_email, subject, html):
    server = os.getenv("MAIL_SERVER")
    if not server:
        print("[DEV MAIL] to:", to_email, "subject:", subject, "html:", html)
        return
    port = int(os.getenv("MAIL_PORT", "587"))
    username = os.getenv("MAIL_USERNAME")
    password = os.getenv("MAIL_PASSWORD")
    use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    use_ssl = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    sender = os.getenv("MAIL_SENDER", username)

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content("HTML 메일을 확인해주세요.", subtype="plain")
    msg.add_alternative(html, subtype="html")

    if use_ssl:
        with smtplib.SMTP_SSL(server, port) as s:
            if username and password: s.login(username, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(server, port) as s:
            if use_tls: s.starttls()
            if username and password: s.login(username, password)
            s.send_message(msg)

def mail_verify_link(email):
    token = serializer().dumps(email)
    link = urljoin(app_base()+"/", url_for("verify_email", token=token).lstrip("/"))
    html = f"<p>아래 링크를 클릭해 이메일을 인증하세요.</p><p><a href='{link}'>{link}</a></p>"
    send_mail(email, "[별내위키] 이메일 인증", html)

def mail_reset_link(email):
    token = serializer().dumps(email, salt="reset")
    link = urljoin(app_base()+"/", url_for("reset", token=token).lstrip("/"))
    html = f"<p>아래 링크에서 새 비밀번호를 설정하세요.</p><p><a href='{link}'>{link}</a></p>"
    send_mail(email, "[별내위키] 비밀번호 재설정", html)

def add_log(action, target=None, details=None):
    db.session.add(Log(user_email=(current_user.email if current_user.is_authenticated else None),
                       action=action, target=target, details=details))
    db.session.commit()

# --- routes ---
@app.route("/")
def index():
    docs = (db.session.query(Document)
            .order_by(Document.created_at.desc()).all())
    out = []
    for d in docs:
        email = None
        if d.author_id:
            u = db.session.get(User, d.author_id)
            email = u.email if u else None
        out.append(type("Row", (), dict(title=d.title, created_at=d.created_at, author_email=email)))
    return render_template("index.html", documents=out)

@app.route("/logs")
def logs():
    rows = db.session.query(Log).order_by(Log.created_at.desc()).limit(500).all()
    return render_template("logs.html", rows=rows)

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["password"]
        if db.session.query(User).filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.")
            return redirect(url_for("register"))
        u = User(email=email)
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        add_log("register", email, "회원가입")
        try:
            mail_verify_link(email)
            flash("인증 메일을 보냈습니다. 메일함을 확인하세요.")
        except Exception as e:
            flash("메일 전송에 실패했지만 계정은 생성되었습니다. 나중에 인증을 재시도하세요.")
        return redirect(url_for("verify_wait", email=email))
    return render_template("register.html")

@app.route("/verify-wait")
def verify_wait():
    email = request.args.get("email","")
    return render_template("verify_wait.html", email=email)

@app.route("/resend-verification", methods=["POST"])
def resend_verification():
    email = request.form.get("email","").strip().lower()
    u = db.session.query(User).filter_by(email=email).first()
    if u:
        try:
            mail_verify_link(email)
            flash("인증 메일을 재발송했습니다.")
            add_log("resend_verification", email)
        except Exception:
            flash("메일 전송에 실패했습니다.")
    else:
        flash("해당 이메일의 계정을 찾을 수 없습니다.")
    return redirect(url_for("verify_wait", email=email))

@app.route("/verify/<token>")
def verify_email(token):
    try:
        email = serializer().loads(token, max_age=60*60*24)  # 24h
    except SignatureExpired:
        flash("토큰이 만료되었습니다.")
        return redirect(url_for("index"))
    except BadSignature:
        flash("토큰이 올바르지 않습니다.")
        return redirect(url_for("index"))
    u = db.session.query(User).filter_by(email=email).first()
    if not u:
        flash("계정을 찾을 수 없습니다.")
        return redirect(url_for("index"))
    if not u.email_verified:
        u.email_verified = True
        db.session.commit()
        add_log("verify_email", email)
        flash("이메일 인증이 완료되었습니다. 로그인 해주세요.")
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["password"]
        u = db.session.query(User).filter_by(email=email).first()
        if not u or not u.check_password(pw):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.")
            return redirect(url_for("login"))
        if not u.email_verified:
            return redirect(url_for("verify_wait", email=email))
        login_user(u)
        add_log("login", email)
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    add_log("logout", current_user.email)
    logout_user()
    flash("로그아웃 되었습니다.")
    return redirect(url_for("index"))

@app.route("/forgot", methods=["GET","POST"])
def forgot():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        u = db.session.query(User).filter_by(email=email).first()
        if u:
            try:
                mail_reset_link(email)
                add_log("send_reset", email)
            except Exception:
                pass
        flash("해당 이메일이 존재한다면 재설정 메일을 보냈습니다.")
        return redirect(url_for("login"))
    return render_template("forgot.html")

@app.route("/reset/<token>", methods=["GET","POST"])
def reset(token):
    try:
        email = serializer().loads(token, salt="reset", max_age=60*60*24)
    except SignatureExpired:
        flash("토큰이 만료되었습니다.")
        return redirect(url_for("login"))
    except BadSignature:
        flash("토큰이 올바르지 않습니다.")
        return redirect(url_for("login"))
    u = db.session.query(User).filter_by(email=email).first()
    if not u:
        flash("계정을 찾을 수 없습니다.")
        return redirect(url_for("login"))
    if request.method == "POST":
        pw = request.form["password"]
        u.set_password(pw)
        db.session.commit()
        add_log("reset_password", email)
        flash("비밀번호가 변경되었습니다. 로그인 해주세요.")
        return redirect(url_for("login"))
    return render_template("reset.html")

@app.route("/delete-account")
@login_required
def delete_account():
    email = current_user.email
    # 문서 소유 정보만 제거 (문서 자체는 유지)
    db.session.query(Document).filter_by(author_id=current_user.id).update({"author_id": None})
    logout_user()
    u = db.session.query(User).filter_by(email=email).first()
    if u:
        db.session.delete(u)
    db.session.commit()
    add_log("delete_account", email)
    flash("계정이 삭제되었습니다.")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
