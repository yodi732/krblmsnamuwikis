
import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, inspect
from werkzeug.security import generate_password_hash, check_password_hash

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

def ensure_schema():
    """Create tables and add missing columns for older DBs."""
    db.create_all()
    insp = inspect(db.engine)
    # add user_email column to logs if missing
    if insp.has_table("log"):
        cols = {c["name"] for c in insp.get_columns("log")}
        if "user_email" not in cols:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE log ADD COLUMN user_email VARCHAR(255)"))

    # created_at/parent_id for document (for older DBs)
    if insp.has_table("document"):
        cols = {c["name"] for c in insp.get_columns("document")}
        with db.engine.begin() as conn:
            if "created_at" not in cols:
                conn.execute(text("ALTER TABLE document ADD COLUMN created_at TIMESTAMPTZ DEFAULT now() NOT NULL"))
            if "parent_id" not in cols:
                conn.execute(text("ALTER TABLE document ADD COLUMN parent_id INTEGER NULL"))

with app.app_context():
    ensure_schema()

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

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email.endswith(ALLOW_DOMAIN):
            flash(f"학교 이메일만 가입할 수 있습니다. 예: abcd{ALLOW_DOMAIN}", "danger")
            return redirect(url_for("signup"))
        if len(password) < 6:
            flash("비밀번호는 최소 6자 이상이어야 합니다.", "danger")
            return redirect(url_for("signup"))
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다. 로그인 해주세요.", "warning")
            return redirect(url_for("login"))

        user = User(email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash("가입이 완료되었습니다. 로그인 해주세요.", "success")
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

@app.route("/create", methods=["GET", "POST"])
@login_required
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
