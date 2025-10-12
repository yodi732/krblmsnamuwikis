import os
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local.db")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ------------- Models -------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # hashed
    email_verified = db.Column(db.Boolean, default=False)
    agreed_at = db.Column(db.DateTime)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    children = db.relationship("Document", cascade="all, delete-orphan")

class ActionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(20))
    doc_id = db.Column(db.Integer)
    user_email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    email = db.Column(db.String(120))
    mail_type = db.Column(db.String(50))  # 'verification' | 'reset'
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

class LoginAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120))
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ------------- Utils -------------
def serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"])

def send_mail(to_email, subject, html_body, mail_type=None, user=None):
    host = os.environ.get("SMTP_HOST")
    user_name = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    port = int(os.environ.get("SMTP_PORT", "587"))
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    sender = os.environ.get("SENDER_EMAIL", user_name)

    if not host or not user_name or not password or not sender:
        print("[WARN] SMTP env not set. Skipping actual send.")
        return

    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    s = smtplib.SMTP(host, port)
    if use_tls:
        s.starttls()
    s.login(user_name, password)
    s.sendmail(sender, [to_email], msg.as_string())
    s.quit()

    # log
    if mail_type and user:
        m = MailLog(user_id=user.id, email=to_email, mail_type=mail_type)
        db.session.add(m)
        db.session.commit()

def verified_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.email_verified:
            flash("이메일 인증 후 이용하세요.", "warning")
            return redirect(url_for("verify_sent"))
        return func(*args, **kwargs)
    return wrapper

# ------------- Login manager -------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------- Routes -------------
@app.route("/")
def index():
    tops = Document.query.filter_by(parent_id=None).order_by(Document.created_at.desc()).all()
    # eager load children
    for t in tops:
        t.children = Document.query.filter_by(parent_id=t.id).all()
    return render_template("index.html", top_docs=tops, can_modify=current_user.is_authenticated and current_user.email_verified)

@app.route("/create", methods=["GET", "POST"])
@login_required
@verified_required
def create_document():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        doc_type = request.form.get("doc_type")
        parent_id = request.form.get("parent_id")

        if not title:
            flash("제목을 입력하세요.", "error")
            return redirect(url_for("create_document"))

        if doc_type == "child":
            if not parent_id:
                flash("상위 문서를 선택하세요.", "error")
                return redirect(url_for("create_document"))
            # disallow subchild
            parent = Document.query.get(int(parent_id))
            if parent.parent_id is not None:
                flash("하위 문서의 하위 문서는 만들 수 없습니다.", "error")
                return redirect(url_for("create_document"))
            newdoc = Document(title=title, content=content, parent_id=parent.id)
        else:
            newdoc = Document(title=title, content=content, parent_id=None)

        db.session.add(newdoc)
        db.session.commit()

        db.session.add(ActionLog(action="CREATE", doc_id=newdoc.id, user_email=current_user.email))
        db.session.commit()

        flash("문서를 만들었습니다.", "success")
        return redirect(url_for("index"))

    tops = Document.query.filter_by(parent_id=None).order_by(Document.created_at.desc()).all()
    return render_template("create.html", top_docs=tops)

@app.post("/delete/<int:doc_id>")
@login_required
@verified_required
def delete_document(doc_id):
    d = Document.query.get_or_404(doc_id)
    db.session.delete(d)
    db.session.commit()
    db.session.add(ActionLog(action="DELETE", doc_id=doc_id, user_email=current_user.email))
    db.session.commit()
    flash("삭제했습니다.", "info")
    return redirect(url_for("index"))

@app.route("/logs")
def action_logs():
    logs = ActionLog.query.order_by(ActionLog.created_at.desc()).limit(100).all()
    return render_template("logs.html", logs=logs)

# ------- Auth -------
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        agree = request.form.get("agree") == "on"

        if not email.endswith("@bl-m.kr"):
            flash("@bl-m.kr 이메일만 가입할 수 있습니다.", "error")
            return redirect(url_for("register"))
        if not agree:
            flash("약관 및 개인정보처리방침에 동의해야 합니다.", "error")
            return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "error")
            return redirect(url_for("register"))

        u = User(email=email, password=generate_password_hash(password), agreed_at=datetime.utcnow())
        db.session.add(u)
        db.session.commit()

        # send verification
        token = serializer().dumps(email)
        link = url_for("verify_email", token=token, _external=True)
        html = f"<p>별내위키 이메일 인증 링크: <a href='{link}'>{link}</a></p>"
        send_mail(email, "[별내위키] 이메일 인증", html, mail_type="verification", user=u)

        login_user(u)
        flash("인증 메일을 보냈습니다. 메일함을 확인하세요.", "info")
        return redirect(url_for("verify_sent"))
    return render_template("register.html")

@app.route("/verify-sent")
@login_required
def verify_sent():
    if current_user.email_verified:
        return redirect(url_for("index"))
    return render_template("verify_sent.html")

@app.post("/resend-verification")
@login_required
def resend_verification():
    token = serializer().dumps(current_user.email)
    link = url_for("verify_email", token=token, _external=True)
    html = f"<p>별내위키 이메일 인증 링크: <a href='{link}'>{link}</a></p>"
    send_mail(current_user.email, "[별내위키] 이메일 인증", html, mail_type="verification", user=current_user)
    flash("인증 메일을 다시 보냈습니다.", "info")
    return redirect(url_for("verify_sent"))

@app.get("/verify/<token>")
def verify_email(token):
    try:
        email = serializer().loads(token, max_age=60*60*24)  # 24h
    except SignatureExpired:
        flash("인증 링크가 만료되었습니다.", "error")
        return redirect(url_for("login"))
    except BadSignature:
        flash("유효하지 않은 링크입니다.", "error")
        return redirect(url_for("login"))

    u = User.query.filter_by(email=email).first_or_404()
    u.email_verified = True
    db.session.commit()
    flash("이메일 인증이 완료되었습니다.", "success")
    return redirect(url_for("index"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        # rate limit: 10 attempts in last 24 hours per email
        since = datetime.utcnow() - timedelta(days=1)
        attempts = LoginAttempt.query.filter(LoginAttempt.email==email, LoginAttempt.attempted_at>=since).count()
        if attempts >= 10:
            flash("로그인 시도 한도를 초과했습니다. 24시간 후 다시 시도하세요.", "error")
            return redirect(url_for("login"))

        user = User.query.filter_by(email=email).first()
        ok = user and check_password_hash(user.password, password)
        if not ok:
            db.session.add(LoginAttempt(email=email))
            db.session.commit()
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return redirect(url_for("login"))

        # success: clear attempts for this email in last day (optional)
        LoginAttempt.query.filter(LoginAttempt.email==email, LoginAttempt.attempted_at>=since).delete()
        db.session.commit()

        login_user(user)
        flash("로그인되었습니다.", "success")
        return redirect(url_for("index"))
    return render_template("login.html")

@app.get("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("index"))

@app.route("/forgot", methods=["GET","POST"])
def forgot():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = serializer().dumps(email)
            link = url_for("reset_password", token=token, _external=True)
            html = f"<p>비밀번호 재설정 링크: <a href='{link}'>{link}</a></p>"
            send_mail(email, "[별내위키] 비밀번호 재설정", html, mail_type="reset", user=user)
        flash("해당 이메일이 존재할 경우 재설정 메일을 보냈습니다.", "info")
        return redirect(url_for("login"))
    return render_template("forgot.html")

@app.route("/reset/<token>", methods=["GET","POST"])
def reset_password(token):
    try:
        email = serializer().loads(token, max_age=60*60*24)
    except SignatureExpired:
        flash("링크가 만료되었습니다.", "error")
        return redirect(url_for("login"))
    except BadSignature:
        flash("유효하지 않은 링크입니다.", "error")
        return redirect(url_for("login"))

    user = User.query.filter_by(email=email).first_or_404()
    if request.method == "POST":
        newpw = request.form["password"]
        user.password = generate_password_hash(newpw)
        db.session.commit()
        flash("비밀번호가 변경되었습니다. 새 비밀번호로 로그인하세요.", "success")
        return redirect(url_for("login"))
    return render_template("reset.html")

@app.post("/delete_account")
@login_required
def delete_account():
    user = current_user

    # anonymize user's logs
    ActionLog.query.filter_by(user_email=user.email).update({ActionLog.user_email: "deleted_user"})
    MailLog.query.filter_by(user_id=user.id).delete()

    db.session.delete(user)
    db.session.commit()
    logout_user()
    flash("회원 정보가 완전히 삭제되었습니다.", "info")
    return redirect(url_for("index"))

@app.get("/privacy")
def privacy():
    return render_template("privacy.html", today=datetime.utcnow().strftime("%Y-%m-%d"))

@app.get("/terms")
def terms():
    return render_template("terms.html")

if __name__ == "__main__":
    app.run(debug=True)
