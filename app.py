
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

# --- App & DB setup ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("EXTERNAL_DATABASE_URL") or "sqlite:///bnwiki.db"
# render.com sometimes provides DATABASE_URL starting with postgres://; SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    # legal/terms/privacy marker (these should not appear as normal docs)
    is_legal = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship("Document", remote_side=[id], backref="children")

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # create/update/delete/login/logout
    doc_title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Utility ---
def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return User.query.get(uid)

def require_login():
    if not current_user():
        flash("로그인이 필요합니다.", "warn")
        return redirect(url_for("login", next=request.path))

def log_action(user_email, action, doc_title=None):
    log = AuditLog(user_email=user_email, action=action, doc_title=doc_title)
    db.session.add(log)
    db.session.commit()

# --- bootstrap DB (create tables + safe migrations) ---
with app.app_context():
    db.create_all()
    # add columns if missing (for existing Postgres dbs)
    try:
        # Add is_legal to document if missing
        if db.engine.url.get_backend_name().startswith("postgres"):
            db.session.execute(text("ALTER TABLE document ADD COLUMN IF NOT EXISTS is_legal BOOLEAN DEFAULT FALSE;"))
            db.session.execute(text("ALTER TABLE document ALTER COLUMN is_legal SET DEFAULT FALSE;"))
            db.session.commit()
    except Exception as e:
        db.session.rollback()
    # Seed legal pages if not present
    terms = Document.query.filter_by(is_legal=True, title="이용약관").first()
    if not terms:
        db.session.add(Document(title="이용약관", content="여기에 이용약관 전문을 입력하세요.", is_legal=True))
    privacy = Document.query.filter_by(is_legal=True, title="개인정보처리방침").first()
    if not privacy:
        db.session.add(Document(title="개인정보처리방침", content="여기에 개인정보처리방침 전문을 입력하세요.", is_legal=True))
    db.session.commit()

# --- Routes ---

@app.route("/")
def index():
    # group by top-level parents (excluding legal docs)
    top_docs = Document.query.filter_by(parent_id=None, is_legal=False).order_by(Document.updated_at.desc()).all()
    return render_template("index.html", user=current_user(), top_docs=top_docs)

@app.route("/docs/<int:doc_id>")
def doc_detail(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.is_legal:
        # redirect to dedicated legal routes to keep UX consistent
        if doc.title == "이용약관":
            return redirect(url_for("terms"))
        if doc.title == "개인정보처리방침":
            return redirect(url_for("privacy"))
    return render_template("doc_detail.html", user=current_user(), doc=doc)

@app.route("/docs/new", methods=["GET", "POST"])
def doc_new():
    if not current_user():
        return require_login()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        parent_id = request.form.get("parent_id")
        parent = Document.query.get(int(parent_id)) if parent_id and parent_id != "none" else None
        # allow only one level: cannot create child-of-child
        if parent and parent.parent_id is not None:
            flash("하위문서의 하위문서는 만들 수 없습니다.", "warn")
            return redirect(url_for("doc_new"))
        if not title:
            flash("제목을 입력하세요.", "warn")
            return redirect(url_for("doc_new"))
        doc = Document(title=title, content=content, parent=parent)
        db.session.add(doc)
        db.session.commit()
        log_action(current_user().email, "create", doc.title)
        return redirect(url_for("index"))
    parents = Document.query.filter_by(parent_id=None, is_legal=False).order_by(Document.title.asc()).all()
    return render_template("doc_new.html", user=current_user(), parents=parents)

@app.route("/docs/<int:doc_id>/delete", methods=["POST"])
def doc_delete(doc_id):
    if not current_user():
        return require_login()
    doc = Document.query.get_or_404(doc_id)
    if doc.is_legal:
        abort(403)
    title = doc.title
    # delete children first
    for child in list(doc.children):
        db.session.delete(child)
    db.session.delete(doc)
    db.session.commit()
    log_action(current_user().email, "delete", title)
    return redirect(url_for("index"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        u = User.query.filter_by(email=email).first()
        if u and u.check_password(pw):
            session["uid"] = u.id
            log_action(u.email, "login")
            return redirect(request.args.get("next") or url_for("index"))
        flash("로그인 정보가 올바르지 않습니다.", "warn")
    return render_template("login.html", user=current_user())

@app.route("/logout")
def logout():
    u = current_user()
    if u:
        log_action(u.email, "logout")
    session.pop("uid", None)
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        pw2 = request.form.get("password2", "")
        agree1 = request.form.get("agree1")
        agree2 = request.form.get("agree2")
        if not email or not pw:
            flash("이메일과 비밀번호를 입력하세요.", "warn")
            return redirect(url_for("signup"))
        if pw != pw2:
            flash("비밀번호 확인이 일치하지 않습니다.", "warn")
            return redirect(url_for("signup"))
        if not (agree1 and agree2):
            flash("약관에 동의해야 가입할 수 있습니다.", "warn")
            return redirect(url_for("signup"))
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "warn")
            return redirect(url_for("signup"))
        u = User(email=email)
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        session["uid"] = u.id
        log_action(u.email, "signup")
        return redirect(url_for("index"))
    return render_template("signup.html", user=current_user())

@app.route("/account/delete", methods=["POST"])
def account_delete():
    if not current_user():
        return require_login()
    u = current_user()
    email = u.email
    session.pop("uid", None)
    # optionally, keep docs; here we only delete user
    db.session.delete(u)
    db.session.commit()
    log_action(email, "account_delete")
    return redirect(url_for("index"))

# --- Logs (requires login) ---
@app.route("/logs")
def view_logs():
    if not current_user():
        return require_login()
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(500).all()
    return render_template("logs.html", user=current_user(), logs=logs)

# --- Legal pages (not editable, not deletable, not in normal list) ---
@app.route("/legal/terms")
def terms():
    doc = Document.query.filter_by(is_legal=True, title="이용약관").first()
    return render_template("legal.html", title="이용약관", content=doc.content if doc else "")

@app.route("/legal/privacy")
def privacy():
    doc = Document.query.filter_by(is_legal=True, title="개인정보처리방침").first()
    return render_template("legal.html", title="개인정보처리방침", content=doc.content if doc else "")

# --- Context processors ---
@app.context_processor
def inject_common():
    return {"year": datetime.utcnow().year}

# --- WSGI ---
if __name__ == "__main__":
    app.run(debug=True)
