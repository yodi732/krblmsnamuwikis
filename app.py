
import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from sqlalchemy import text, func
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///app.db")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ---------- Models ----------
class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    def set_password(self, pw: str):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_email = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255))
    action = db.Column(db.String(50))
    target = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

# ---------- DB bootstrap & self-heal ----------
with app.app_context():
    db.create_all()
    # self-heal missing columns for existing DBs (esp. Postgres on Render)
    insp = db.inspect(db.engine)
    cols = {c["name"] for c in insp.get_columns("document")}
    if "updated_at" not in cols:
        # Postgres uses TIMESTAMPTZ, SQLite accepts TIMESTAMP
        try:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE document ADD COLUMN updated_at TIMESTAMPTZ"))
                conn.execute(text("UPDATE document SET updated_at = created_at WHERE updated_at IS NULL"))
        except Exception:
            # Fallback for SQLite
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE document ADD COLUMN updated_at TIMESTAMP"))
                conn.execute(text("UPDATE document SET updated_at = created_at WHERE updated_at IS NULL"))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------- Helpers ----------
def log(action:str, target:str|None=None):
    try:
        db.session.add(AuditLog(email=(current_user.email if current_user.is_authenticated else None),
                                action=action, target=target))
        db.session.commit()
    except Exception:
        db.session.rollback()

# ---------- Routes ----------
@app.route("/")
def index():
    docs = Document.query.order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/logs")
@login_required
def logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(500).all()
    return render_template("logs.html", logs=logs)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        agree = request.form.get("agree")
        if not agree:
            return render_template("register.html", error="약관 동의가 필요합니다.")
        if User.query.filter_by(email=email).first():
            return render_template("register.html", error="이미 가입된 이메일입니다.")
        u = User(email=email)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        log("register", email)
        login_user(u)
        return redirect(url_for("index"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        # robust login without legacy 'password' column
        row = db.session.execute(
            text('SELECT id, email, password_hash FROM "user" WHERE email=:email LIMIT 1'),
            {"email": email}
        ).first()
        if not row:
            return render_template("login.html", error="계정을 찾을 수 없습니다.")
        # check hash
        if not check_password_hash(row.password_hash, password):
            return render_template("login.html", error="비밀번호가 올바르지 않습니다.")
        u = User.query.get(row.id)
        login_user(u)
        log("login", email)
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    log("logout", current_user.email)
    logout_user()
    return redirect(url_for("index"))

@app.route("/document/new", methods=["GET","POST"])
@login_required
def new_document():
    if request.method == "POST":
        title = request.form.get("title") or ""
        content = request.form.get("content") or ""
        doc = Document(title=title, content=content, author_email=current_user.email)
        db.session.add(doc)
        db.session.commit()
        log("create_document", f"{doc.id}:{doc.title}")
        return redirect(url_for("index"))
    return render_template("document_form.html", doc=None)

@app.route("/document/<int:doc_id>/edit", methods=["GET","POST"])
@login_required
def edit_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if request.method == "POST":
        doc.title = request.form.get("title") or doc.title
        doc.content = request.form.get("content") or doc.content
        doc.updated_at = datetime.utcnow()
        db.session.commit()
        log("update_document", f"{doc.id}:{doc.title}")
        return redirect(url_for("index"))
    return render_template("document_form.html", doc=doc)

@app.route("/document/<int:doc_id>/delete")
@login_required
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    title = doc.title
    db.session.delete(doc)
    db.session.commit()
    log("delete_document", f"{doc_id}:{title}")
    return redirect(url_for("index"))

@app.route("/account/delete")
@login_required
def delete_account():
    email = current_user.email
    # delete user's documents
    Document.query.filter_by(author_email=email).delete()
    # delete user
    u = User.query.get(current_user.id)
    logout_user()
    db.session.delete(u)
    db.session.commit()
    log("delete_account", email)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
