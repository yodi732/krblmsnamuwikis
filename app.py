
import os
from datetime import datetime
from functools import wraps
from email.message import EmailMessage
import smtplib

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, inspect
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

ALLOW_DOMAIN = "@bl-m.kr"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///local.db")
uri = app.config["SQLALCHEMY_DATABASE_URI"]
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
if uri.startswith("postgresql://") and "+psycopg" not in uri:
    uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = uri

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

db = SQLAlchemy(app)

# -------------------- Models --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    email_verified = db.Column(db.Boolean, default=False)
    agreed_at = db.Column(db.DateTime, nullable=True)  # 개인정보/약관 동의 일시

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id', ondelete='CASCADE'), nullable=True)
    children = db.relationship(
        'Document',
        cascade='all, delete-orphan',
        backref=db.backref('parent', remote_side='Document.id'),
        lazy='select'
    )

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(20), nullable=False)
    doc_id = db.Column(db.Integer, nullable=False)
    user_email = db.Column(db.String(255), nullable=True)  # 로그인 사용자 이메일 기록

# -------------------- Helpers --------------------
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return User.query.get(uid)

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("로그인이 필요합니다.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def verified_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        cu = current_user()
        if not (cu and cu.email_verified):
            flash("이메일 인증 후 이용할 수 있습니다.", "warning")
            return redirect(url_for("resend_verification"))
        return view(*args, **kwargs)
    return wrapped

def ensure_schema():
    """Create tables and add missing columns for older DBs."""
    db.create_all()
    insp = inspect(db.engine)
    # Log.user_email
    if insp.has_table("log"):
        cols = {c["name"] for c in insp.get_columns("log")}
        if "user_email" not in cols:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE log ADD COLUMN user_email VARCHAR(255)"))
    # Document columns
    if insp.has_table("document"):
        cols = {c["name"] for c in insp.get_columns("document")}
        with db.engine.begin() as conn:
            if "created_at" not in cols:
                conn.execute(text("ALTER TABLE document ADD COLUMN created_at TIMESTAMPTZ DEFAULT now() NOT NULL"))
            if "parent_id" not in cols:
                conn.execute(text("ALTER TABLE document ADD COLUMN parent_id INTEGER NULL"))
    # User.email_verified, User.agreed_at
    if insp.has_table("user"):
        cols = {c["name"] for c in insp.get_columns("user")}
        with db.engine.begin() as conn:
            if "email_verified" not in cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN email_verified BOOLEAN DEFAULT FALSE'))
            if "agreed_at" not in cols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN agreed_at TIMESTAMPTZ NULL'))

with app.app_context():
    ensure_schema()

# token utils
def _serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"])

def generate_token(email: str, purpose: str) -> str:
    return _serializer().dumps(email, salt=f"purpose:{purpose}")

def confirm_token(token: str, purpose: str, max_age=60*60*24):
    return _serializer().loads(token, salt=f"purpose:{purpose}", max_age=max_age)

# email util
def send_email(to_email: str, subject: str, body: str):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pw   = os.getenv("SMTP_PASS")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    sender = os.getenv("SENDER_EMAIL", user)

    if not (host and port and user and pw and sender):
        app.logger.error("SMTP env vars missing; cannot send email.")
        return False

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if port == 465:
        with smtplib.SMTP_SSL(host, port) as s:
            s.login(user, pw)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            if use_tls:
                s.starttls()
            s.login(user, pw)
            s.send_message(msg)
    return True

# -------------------- Routes --------------------
@app.context_processor
def inject_user():
    return {"current_user": current_user()}

@app.route("/")
def index():
    parents = (Document.query
               .filter_by(parent_id=None)
               .order_by(Document.created_at.desc())
               .all())
    return render_template("index.html", parents=parents)

# ---- Static policy pages
@app.get("/privacy")
def privacy():
    return render_template("privacy.html")

@app.get("/terms")
def terms():
    return render_template("terms.html")

# ---- Auth
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        agree = request.form.get("agree")  # "on" if checked

        if not email.endswith(ALLOW_DOMAIN):
            flash(f"학교 이메일만 가입할 수 있습니다. 예: abcd{ALLOW_DOMAIN}", "danger")
            return redirect(url_for("signup"))
        if len(password) < 6:
            flash("비밀번호는 최소 6자 이상이어야 합니다.", "danger")
            return redirect(url_for("signup"))
        if not agree:
            flash("개인정보처리방침 및 이용약관에 동의해야 가입할 수 있습니다.", "danger")
            return redirect(url_for("signup"))
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다. 로그인 해주세요.", "warning")
            return redirect(url_for("login"))

        user = User(email=email, password_hash=generate_password_hash(password), agreed_at=datetime.utcnow())
        db.session.add(user)
        db.session.commit()

        # send verification mail
        token = generate_token(email, "verify")
        link  = url_for("verify_email", token=token, _external=True)
        ok = send_email(
            to_email=email,
            subject="[별내위키] 이메일 인증을 완료해주세요",
            body=f"안녕하세요!\n\n아래 링크를 눌러 이메일 인증을 완료해주세요:\n{link}\n\n(24시간 이내 유효)"
        )
        if ok:
            flash("가입 완료! 이메일 인증 링크를 확인해주세요.", "success")
        else:
            flash("가입은 완료되었지만 메일 전송에 실패했습니다. 관리자에게 알려주세요.", "warning")
        return redirect(url_for("login"))
    return render_template("signup.html", allow_domain=ALLOW_DOMAIN)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "danger")
            return redirect(url_for("login"))
        if not user.email_verified:
            flash("이메일 인증이 필요합니다. 인증 메일을 재전송할 수 있어요.", "warning")
            return redirect(url_for("resend_verification"))
        session["user_id"] = user.id
        flash("로그인되었습니다.", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("index"))
    return render_template("login.html")

@app.post("/logout")
def logout():
    session.pop("user_id", None)
    flash("로그아웃되었습니다.", "success")
    return redirect(url_for("index"))

@app.get("/verify/<token>")
def verify_email(token):
    try:
        email = confirm_token(token, "verify")
    except SignatureExpired:
        flash("인증 링크가 만료되었습니다. 다시 요청해주세요.", "danger")
        return redirect(url_for("resend_verification"))
    except BadSignature:
        flash("잘못된 인증 링크입니다.", "danger")
        return redirect(url_for("login"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("계정을 찾을 수 없습니다.", "danger")
        return redirect(url_for("signup"))
    if not user.email_verified:
        user.email_verified = True
        db.session.commit()
    flash("이메일 인증이 완료되었습니다. 로그인해주세요.", "success")
    return redirect(url_for("login"))

@app.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("해당 이메일의 계정을 찾을 수 없습니다.", "danger")
            return redirect(url_for("resend_verification"))
        if user.email_verified:
            flash("이미 인증된 계정입니다. 로그인해주세요.", "info")
            return redirect(url_for("login"))
        token = generate_token(email, "verify")
        link  = url_for("verify_email", token=token, _external=True)
        ok = send_email(
            to_email=email,
            subject="[별내위키] 이메일 인증 링크 재전송",
            body=f"다시 인증을 진행해주세요:\n{link}\n(24시간 이내 유효)"
        )
        flash("인증 메일을 다시 보냈습니다." if ok else "메일 전송에 실패했습니다.", "success" if ok else "warning")
        return redirect(url_for("login"))
    return render_template("resend_verification.html")

# ---- Password reset
@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("해당 이메일의 계정을 찾을 수 없습니다.", "danger")
            return redirect(url_for("forgot_password"))
        token = generate_token(email, "reset")
        link  = url_for("reset_password", token=token, _external=True)
        ok = send_email(
            to_email=email,
            subject="[별내위키] 비밀번호 재설정 링크",
            body=f"아래 링크에서 새 비밀번호를 설정해주세요:\n{link}\n(24시간 이내 유효)"
        )
        flash("재설정 메일을 보냈습니다." if ok else "메일 전송 실패. 관리자에게 문의하세요.", "success" if ok else "warning")
        return redirect(url_for("login"))
    return render_template("forgot.html")

@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = confirm_token(token, "reset")
    except SignatureExpired:
        flash("재설정 링크가 만료되었습니다. 다시 요청해주세요.", "danger")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("잘못된 재설정 링크입니다.", "danger")
        return redirect(url_for("login"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("계정을 찾을 수 없습니다.", "danger")
        return redirect(url_for("signup"))

    if request.method == "POST":
        pw = request.form.get("password") or ""
        pw2 = request.form.get("password2") or ""
        if len(pw) < 6:
            flash("비밀번호는 최소 6자 이상이어야 합니다.", "danger")
            return redirect(request.url)
        if pw != pw2:
            flash("비밀번호가 일치하지 않습니다.", "danger")
            return redirect(request.url)
        user.password_hash = generate_password_hash(pw)
        db.session.commit()
        flash("비밀번호가 변경되었습니다. 로그인해주세요.", "success")
        return redirect(url_for("login"))
    return render_template("reset.html", email=email)

# ---- Document CRUD
@app.route("/create", methods=["GET", "POST"])
@login_required
@verified_required
def create_document():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = request.form.get("content") or ""
        doc_type = request.form.get("doc_type", "parent")
        parent_id = request.form.get("parent_id")

        if not title:
            flash("제목을 입력하세요.", "warning")
            return redirect(url_for("create_document"))

        parent = None
        if doc_type == "child":
            if not parent_id:
                flash("하위 문서의 상위 문서를 선택하세요.", "warning")
                return redirect(url_for("create_document"))
            parent = Document.query.get_or_404(int(parent_id))
            if parent.parent_id is not None:
                flash("하위 문서의 하위 문서는 만들 수 없습니다.", "danger")
                return redirect(url_for("create_document"))

        doc = Document(title=title, content=content, parent=parent)
        db.session.add(doc)
        db.session.commit()

        cu = current_user()
        db.session.add(Log(action="CREATE", doc_id=doc.id, user_email=(cu.email if cu else None)))
        db.session.commit()

        return redirect(url_for("create_document"))

    parents = (Document.query
               .filter_by(parent_id=None)
               .order_by(Document.created_at.desc())
               .all())
    return render_template("create.html", parents=parents)

@app.post("/delete/<int:doc_id>")
@login_required
@verified_required
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    db.session.delete(doc)
    db.session.commit()
    cu = current_user()
    db.session.add(Log(action="DELETE", doc_id=doc_id, user_email=(cu.email if cu else None)))
    db.session.commit()
    return redirect(request.referrer or url_for("index"))

@app.route("/logs")
def view_logs():
    logs = Log.query.order_by(Log.time.desc()).limit(500).all()
    return render_template("logs.html", logs=logs)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
