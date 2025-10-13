
import os
import re
import smtplib
from email.mime.text import MIMEText
from urllib.parse import urljoin
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# ----------------------------------------------------------------------------
# App / DB setup
# ----------------------------------------------------------------------------

app = Flask(__name__, static_folder="static", template_folder="templates")

# Secret key
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///app.db")
# Render / Heroku style DATABASE_URL for Postgres may start with postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# email/domain config
ALLOWED_EMAIL_DOMAIN = os.environ.get("ALLOWED_EMAIL_DOMAIN", "@bl-m.kr")

def make_serializer():
    secret = app.config["SECRET_KEY"]
    return URLSafeTimedSerializer(secret, salt="email-signing")

# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    parent_id = db.Column(db.Integer, nullable=True)
    author_email = db.Column(db.String(255), nullable=True)  # <-- ensure exists
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), nullable=True)   # <-- ensure exists
    action = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text, nullable=True)             # <-- ensure exists
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)  # <-- ensure exists

# ----------------------------------------------------------------------------
# Lightweight auto-migration to match expected schema
# ----------------------------------------------------------------------------

def safe_exec(sql):
    try:
        db.session.execute(db.text(sql))
        db.session.commit()
    except Exception as e:
        db.session.rollback()

def ensure_schema():
    # create tables if not exist
    db.create_all()
    # add missing columns (Postgres syntax compatible; SQLite ignores IF NOT EXISTS on add column but safe)
    safe_exec("""ALTER TABLE document ADD COLUMN IF NOT EXISTS author_email VARCHAR(255);""")
    safe_exec("""ALTER TABLE log ADD COLUMN IF NOT EXISTS user_email VARCHAR(255);""")
    safe_exec("""ALTER TABLE log ADD COLUMN IF NOT EXISTS details TEXT;""")
    safe_exec("""ALTER TABLE log ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();""")
    # drop legacy columns if they exist
    safe_exec("""ALTER TABLE log DROP COLUMN IF EXISTS target;""")

with app.app_context():
    ensure_schema()

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def send_email(to_email: str, subject: str, html_body: str):
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes", "on")
    from_addr = os.environ.get("SMTP_FROM", username or "no-reply@localhost")

    if not host or not port:
        app.logger.error("SMTP is not configured")
        raise RuntimeError("SMTP is not configured")

    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        if username and password:
            server.login(username, password)
        server.sendmail(from_addr, [to_email], msg.as_string())

def make_absolute_url(path: str):
    # Build absolute URL for emails
    external_base = os.environ.get("EXTERNAL_BASE_URL")  # e.g., https://krblmsnamuwikis.onrender.com
    if external_base:
        return urljoin(external_base, path)
    # fallback to request-host if available
    try:
        return urljoin(request.url_root, path)
    except Exception:
        return path

def log_action(action: str, details: str = None):
    email = None
    try:
        if current_user.is_authenticated:
            email = current_user.email
    except Exception:
        pass
    entry = Log(user_email=email, action=action, details=details)
    db.session.add(entry)
    db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ----------------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------------

@app.route("/")
def index():
    docs = Document.query.order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.route("/logs")
@login_required
def logs():
    rows = Log.query.order_by(Log.created_at.desc()).limit(500).all()
    return render_template("logs.html", rows=rows)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        agree = request.form.get("agree") == "on"

        if not agree:
            flash("개인정보처리방침과 이용약관에 동의해야 가입할 수 있습니다.", "error")
            return redirect(url_for("register"))

        if not email.endswith(ALLOWED_EMAIL_DOMAIN):
            flash(f"학교 계정(@{ALLOWED_EMAIL_DOMAIN.lstrip('@')})만 가입할 수 있습니다.", "error")
            return redirect(url_for("register"))

        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            flash("이메일 형식이 올바르지 않습니다.", "error")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "error")
            return redirect(url_for("register"))

        user = User(email=email, email_verified=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # send verification email
        s = make_serializer()
        token = s.dumps({"email": email})
        verify_url = make_absolute_url(url_for("verify_email", token=token))
        html = f"""
        <p>안녕하세요. 별내위키 이메일 인증 링크입니다.</p>
        <p><a href="{verify_url}">여기를 클릭하여 인증을 완료하세요</a></p>
        <p>링크가 열리지 않으면 아래 주소를 복사해 브라우저에 붙여넣기 하세요:<br>{verify_url}</p>
        """
        try:
            send_email(email, "[별내위키] 이메일 인증", html)
        except Exception as e:
            app.logger.exception("메일 발송 실패")
            flash("회원가입은 생성되었지만, 인증 메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요.", "error")

        log_action("register", f"new user: {email}")
        return render_template("verify_needed.html", email=email)

    return render_template("register.html", allowed_domain=ALLOWED_EMAIL_DOMAIN)

@app.route("/verify/<token>")
def verify_email(token):
    s = make_serializer()
    try:
        data = s.loads(token, max_age=60*60*24)  # 24h
        email = data.get("email")
    except SignatureExpired:
        flash("인증 링크가 만료되었습니다. 다시 시도해 주세요.", "error")
        return redirect(url_for("login"))
    except BadSignature:
        abort(400)

    user = User.query.filter_by(email=email).first_or_404()
    user.email_verified = True
    db.session.commit()
    log_action("verify_email", f"verified: {email}")
    flash("이메일 인증이 완료되었습니다. 로그인해 주세요.", "success")
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return redirect(url_for("login"))

        if not user.email_verified:
            return render_template("verify_needed.html", email=email)

        login_user(user)
        log_action("login", f"{email} logged in")
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    email = current_user.email
    logout_user()
    log_action("logout", f"{email} logged out")
    return redirect(url_for("index"))

@app.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    email = current_user.email
    u = User.query.get(current_user.id)
    logout_user()
    db.session.delete(u)
    db.session.commit()
    log_action("delete_account", f"{email} deleted account")
    flash("회원탈퇴가 완료되었습니다.", "success")
    return redirect(url_for("index"))

# password reset
@app.route("/reset", methods=["GET", "POST"])
def request_reset():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            s = make_serializer()
            token = s.dumps({"email": email, "purpose": "reset"})
            reset_url = make_absolute_url(url_for("reset_password", token=token))
            html = f"""
            <p>안녕하세요. 별내위키 비밀번호 재설정 링크입니다.</p>
            <p><a href="{reset_url}">여기를 클릭하여 비밀번호를 재설정하세요</a></p>
            <p>링크가 열리지 않으면 아래 주소를 복사해 브라우저에 붙여넣기 하세요:<br>{reset_url}</p>
            """
            try:
                send_email(email, "[별내위키] 비밀번호 재설정", html)
            except Exception:
                app.logger.exception("비번 재설정 메일 발송 실패")
        flash("해당 이메일이 등록되어 있다면 재설정 링크가 전송됩니다.", "success")
        return redirect(url_for("login"))
    return render_template("request_reset.html")

@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    s = make_serializer()
    try:
        data = s.loads(token, max_age=60*60)  # 1h
        if data.get("purpose") != "reset":
            abort(400)
        email = data["email"]
    except Exception:
        abort(400)
    user = User.query.filter_by(email=email).first_or_404()

    if request.method == "POST":
        pw = request.form.get("password") or ""
        if len(pw) < 6:
            flash("비밀번호는 6자 이상이어야 합니다.", "error")
            return redirect(request.url)
        user.set_password(pw)
        db.session.commit()
        log_action("reset_password", f"{email} changed password")
        flash("비밀번호가 변경되었습니다. 로그인해 주세요.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html")

# ----------------------------------------------------------------------------
# Run (for local dev)
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
