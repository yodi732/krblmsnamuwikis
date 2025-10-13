from __future__ import annotations
import os, re, logging, datetime as dt
from urllib.parse import urljoin
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from mailer import SMTPSender

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__, static_url_path="/static", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
db_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
# Render/Heroku compatibility: psycopg scheme normalization
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://") and "+psycopg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycg://")
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ---- Models ----
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)

    def set_password(self, pw: str):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    author_email = db.Column(db.String(255), nullable=True)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, index=True, nullable=False)

@login_manager.user_loader
def load_user(uid: str):
    return User.query.get(int(uid))

# Create tables on startup if not exist
with app.app_context():
    db.create_all()

# ---- Utils ----
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

def app_base_url() -> str:
    base = os.getenv("APP_BASE_URL")
    if base:
        return base.rstrip("/")
    # best-effort from request context
    return request.url_root.rstrip("/") if request else ""

def send_email(subject: str, to: str, text: str, html: str | None = None) -> None:
    sender = SMTPSender()
    ok, err = sender.send(subject, text, [to], html)
    if not ok:
        raise RuntimeError(f"email send failed: {err}")

EMAIL_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "bl-m.kr").lower()

def is_school_email(addr: str) -> bool:
    if not addr or "@" not in addr:
        return False
    local, domain = addr.rsplit("@", 1)
    return domain.lower() == EMAIL_DOMAIN

# ---- Routes ----
@app.get("/")
def index():
    docs = Document.query.order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.get("/register")
def register():
    return render_template("register.html")

@app.post("/register")
def register_post():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    agree = request.form.get("agree") == "on"
    if not is_school_email(email):
        flash(f"학교 계정(@{EMAIL_DOMAIN})만 가입할 수 있습니다.", "error")
        return redirect(url_for("register"))
    if not agree:
        flash("개인정보처리방침 및 이용약관에 동의해야 가입할 수 있습니다.", "error")
        return redirect(url_for("register"))
    if len(password) < 6:
        flash("비밀번호는 6자 이상이어야 합니다.", "error")
        return redirect(url_for("register"))
    if User.query.filter_by(email=email).first():
        flash("이미 가입된 이메일입니다. 로그인해주세요.", "error")
        return redirect(url_for("login"))
    u = User(email=email)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    # Send verification email
    token = serializer.dumps({"email": email}, salt="verify")
    verify_link = urljoin(app_base_url()+"/", url_for("verify_email", token=token).lstrip("/"))
    subject = "별내위키 이메일 인증"
    text = f"별내위키 가입을 완료하려면 아래 링크를 클릭하세요:\n{verify_link}\n링크는 24시간 동안 유효합니다."
    html = f"""<p>별내위키 가입을 완료하려면 아래 버튼을 클릭하세요.</p>
    <p><a href="{verify_link}" style="display:inline-block;padding:10px 16px;border-radius:6px;background:#114a99;color:#fff;text-decoration:none;">이메일 인증하기</a></p>
    <p>버튼이 보이지 않으면 링크를 복사해 브라우저에 붙여넣기: <br><code>{verify_link}</code></p>"""
    try:
        send_email(subject, email, text, html)
    except Exception as e:
        log.exception("Verification email send failed")
        flash("이메일 전송에 실패했습니다. 잠시 후 다시 시도해주세요.", "error")
        return redirect(url_for("login"))
    db.session.add(Log(user_email=email, action="register", details="회원가입"))
    db.session.commit()
    flash("가입 완료! 이메일 인증 링크를 확인해주세요.", "success")
    return redirect(url_for("login"))

@app.get("/verify/<token>")
def verify_email(token: str):
    try:
        data = serializer.loads(token, salt="verify", max_age=60*60*24)
    except SignatureExpired:
        flash("인증 링크가 만료되었습니다. 다시 로그인하여 인증 메일을 요청하세요.", "error")
        return redirect(url_for("login"))
    except BadSignature:
        abort(400)
    email = data.get("email")
    u = User.query.filter_by(email=email).first_or_404()
    if not u.is_verified:
        u.is_verified = True
        db.session.add(Log(user_email=email, action="verify", details="이메일 인증 완료"))
        db.session.commit()
    flash("이메일 인증이 완료되었습니다. 로그인해주세요.", "success")
    return redirect(url_for("login"))

@app.get("/login")
def login():
    return render_template("login.html")

@app.post("/login")
def login_post():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    u = User.query.filter_by(email=email).first()
    if not u or not u.check_password(password):
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
        return redirect(url_for("login"))
    if not u.is_verified:
        flash("이메일 인증 후 로그인할 수 있습니다.", "error")
        return redirect(url_for("login"))
    login_user(u)
    db.session.add(Log(user_email=email, action="login", details="로그인"))
    db.session.commit()
    return redirect(url_for("index"))

@app.post("/logout")
@login_required
def logout():
    db.session.add(Log(user_email=current_user.email, action="logout", details="로그아웃"))
    db.session.commit()
    logout_user()
    return redirect(url_for("index"))

@app.get("/logs")
@login_required
def logs():
    rows = Log.query.order_by(Log.created_at.desc()).limit(500).all()
    return render_template("logs.html", rows=rows)

@app.get("/password/reset")
def password_reset_request():
    return render_template("password_reset_request.html")

@app.post("/password/reset")
def password_reset_request_post():
    email = (request.form.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if user:
        token = serializer.dumps({"email": email}, salt="reset")
        link = urljoin(app_base_url()+"/", url_for("password_reset_form", token=token).lstrip("/"))
        subject = "별내위키 비밀번호 재설정"
        text = f"아래 링크에서 비밀번호를 재설정하세요:\n{link}\n링크는 1시간 동안 유효합니다."
        html = f'<p>아래 버튼을 눌러 비밀번호를 재설정하세요.</p><p><a href="{link}" style="display:inline-block;padding:10px 16px;border-radius:6px;background:#114a99;color:#fff;text-decoration:none;">비밀번호 재설정</a></p>'
        try:
            send_email(subject, email, text, html)
        except Exception as e:
            log.exception("Password reset email send failed")
            flash("이메일 전송에 실패했습니다. 잠시 후 다시 시도해주세요.", "error")
            return redirect(url_for("password_reset_request"))
        db.session.add(Log(user_email=email, action="password_reset_request", details="재설정 메일 발송"))
        db.session.commit()
    # 보안상 항상 성공 메시지
    flash("비밀번호 재설정 링크를 이메일로 보냈습니다(등록된 경우).", "success")
    return redirect(url_for("login"))

@app.get("/password/reset/<token>")
def password_reset_form(token: str):
    return render_template("password_reset_form.html", token=token)

@app.post("/password/reset/<token>")
def password_reset_submit(token: str):
    try:
        data = serializer.loads(token, salt="reset", max_age=60*60)
    except SignatureExpired:
        flash("링크가 만료되었습니다. 다시 요청해주세요.", "error")
        return redirect(url_for("password_reset_request"))
    except BadSignature:
        abort(400)
    email = data.get("email")
    u = User.query.filter_by(email=email).first_or_404()
    pw = request.form.get("password") or ""
    if len(pw) < 6:
        flash("비밀번호는 6자 이상이어야 합니다.", "error")
        return redirect(url_for("password_reset_form", token=token))
    u.set_password(pw)
    db.session.add(Log(user_email=email, action="password_reset", details="비밀번호 변경"))
    db.session.commit()
    flash("비밀번호가 변경되었습니다. 로그인해주세요.", "success")
    return redirect(url_for("login"))

@app.get("/delete")
@login_required
def delete_confirm():
    return render_template("delete_account.html")

@app.post("/delete")
@login_required
def delete_account():
    email = current_user.email
    logout_user()
    # 실제 유저 삭제
    User.query.filter_by(email=email).delete()
    db.session.add(Log(user_email=email, action="delete_account", details="회원탈퇴"))
    db.session.commit()
    flash("회원탈퇴가 완료되었습니다.", "success")
    return redirect(url_for("index"))

# Error handlers to avoid 500 noise
@app.errorhandler(400)
def bad_request(e): 
    return render_template("error.html", code=400, message="잘못된 요청입니다."), 400

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="페이지를 찾을 수 없습니다."), 404
