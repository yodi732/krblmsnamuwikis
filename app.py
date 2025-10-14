
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, \
    logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = SECRET_KEY

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ---------- Models ----------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    author_email = db.Column(db.String(255))

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255))
    action = db.Column(db.String(50))
    target = db.Column(db.String(255))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()

# ---------- Helpers ----------
def write_log(action, target, details=""):
    try:
        db.session.add(Log(
            user_email=(current_user.email if current_user.is_authenticated else None),
            action=action, target=target, details=details))
        db.session.commit()
    except Exception:
        db.session.rollback()

# ---------- Routes ----------
@app.route("/")
def index():
    docs = Document.query.order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("로그인되었습니다.", "success")
            return redirect(url_for("index"))
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("로그아웃되었습니다.", "success")
    return redirect(url_for("index"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        pwd = request.form.get("password","")
        agree = request.form.get("agree") == "on"
        if not agree:
            flash("개인정보 처리 및 이용약관에 동의해야 합니다.", "error")
            return render_template("register.html")
        if not email or not pwd or len(pwd) < 6:
            flash("이메일과 비밀번호(6자 이상)를 입력하세요.", "error")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "error")
            return render_template("register.html")
        user = User(email=email, password_hash=generate_password_hash(pwd))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("회원가입 완료!", "success")
        write_log("register", email)
        return redirect(url_for("index"))
    return render_template("register.html")

# ---- Account delete (회원탈퇴)
@app.route("/account/delete", methods=["POST"])
@login_required
def account_delete():
    uid = current_user.id
    email = current_user.email
    # logout first
    logout_user()
    # delete authored docs? Keep docs but note by email.
    user = db.session.get(User, uid)
    if user:
        db.session.delete(user)
        db.session.commit()
    write_log("account_delete", email)
    flash("회원탈퇴가 완료되었습니다.", "success")
    return redirect(url_for("index"))

# ---- Documents CRUD
@app.route("/document/new", methods=["GET", "POST"])
@login_required
def doc_new():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        if not title:
            flash("제목을 입력하세요.", "error")
            return render_template("doc_form.html", mode="new")
        doc = Document(title=title, content=content, author_email=current_user.email)
        db.session.add(doc)
        db.session.commit()
        write_log("create", f"doc:{doc.id}", f"title={title}")
        return redirect(url_for("index"))
    return render_template("doc_form.html", mode="new")

@app.route("/document/<int:doc_id>/edit", methods=["GET", "POST"])
@login_required
def doc_edit(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    if request.method == "POST":
        doc.title = request.form.get("title","").strip() or doc.title
        doc.content = request.form.get("content","")
        db.session.commit()
        write_log("update", f"doc:{doc.id}", f"title={doc.title}")
        return redirect(url_for("index"))
    return render_template("doc_form.html", mode="edit", doc=doc)

@app.route("/document/<int:doc_id>/delete", methods=["POST"])
@login_required
def doc_delete(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    title = doc.title
    db.session.delete(doc)
    db.session.commit()
    write_log("delete", f"doc:{doc_id}", f"title={title}")
    flash("삭제되었습니다.", "success")
    return redirect(url_for("index"))

# ---- Logs
@app.route("/logs")
@login_required
def logs():
    rows = Log.query.order_by(Log.created_at.desc()).limit(500).all()
    return render_template("logs.html", rows=rows)

# ---- Legal pages
@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
