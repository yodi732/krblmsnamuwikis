
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text, inspect
from sqlalchemy.exc import ProgrammingError
from datetime import datetime
import bcrypt
import re

def slugify(title):
    # create a url-safe slug from Korean/English text
    s = title.strip()
    s = re.sub(r'\s+', '-', s)
    s = re.sub(r'[^0-9A-Za-z가-힣\-\_]', '', s)
    return s.lower()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY","super-secret-key")

# DB: prefer DATABASE_URL env (Render)
db_url = os.environ.get("DATABASE_URL", "sqlite:///wiki.db")
# Render sometimes supplies postgresql://; SQLAlchemy with psycopg needs postgresql+psycopg://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    slug = db.Column(db.String(255), unique=True, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.LargeBinary(60), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    meta = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

def ensure_columns():
    # Add columns if missing (for existing DBs)
    insp = inspect(db.engine)
    cols = {c['name'] for c in insp.get_columns('document')} if insp.has_table('document') else set()
    with db.engine.begin() as conn:
        if not insp.has_table("document"):
            db.create_all()
        else:
            if 'slug' not in cols:
                conn.execute(text("ALTER TABLE document ADD COLUMN slug VARCHAR(255)"))
                try:
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_slug ON document (slug)"))
                except Exception:
                    pass
            if 'updated_at' not in cols:
                conn.execute(text("ALTER TABLE document ADD COLUMN updated_at TIMESTAMP WITHOUT TIME ZONE"))
                conn.execute(text("UPDATE document SET updated_at = COALESCE(updated_at, created_at)"))
                conn.execute(text("ALTER TABLE document ALTER COLUMN updated_at SET NOT NULL"))
        # create other tables if missing
        db.create_all()

def log(action, meta=""):
    try:
        uid = session.get("user_id")
        db.session.add(AuditLog(user_id=uid, action=action, meta=meta))
        db.session.commit()
    except Exception:
        db.session.rollback()

@app.before_request
def attach_user():
    g = globals()
    g['current_user'] = None
    uid = session.get("user_id")
    if uid:
        g['current_user'] = User.query.get(uid)

@app.route("/")
def index():
    docs = Document.query.order_by(Document.updated_at.desc()).all()
    # sidebar (목차) : simple top-level list
    sidebar = Document.query.order_by(Document.title.asc()).limit(10).all()
    return render_template("index.html", docs=docs, sidebar=sidebar)

@app.route("/doc/<slug>")
def doc_view(slug):
    d = Document.query.filter_by(slug=slug).first_or_404()
    return render_template("document.html", d=d)

@app.route("/create", methods=["GET","POST"])
def create_doc():
    if request.method == "POST":
        title = request.form["title"].strip()
        content = request.form.get("content","")
        s = request.form.get("slug") or slugify(title)
        if not title:
            flash("제목을 입력하세요.", "error")
            return redirect(url_for("create_doc"))
        if Document.query.filter_by(slug=s).first():
            flash("같은 슬러그의 문서가 이미 있습니다.", "error")
            return redirect(url_for("create_doc"))
        d = Document(title=title, content=content, slug=s)
        db.session.add(d)
        db.session.commit()
        log("create_document", f"title={title}")
        return redirect(url_for("doc_view", slug=d.slug))
    return render_template("create.html")

@app.route("/edit/<slug>", methods=["GET","POST"])
def edit_doc(slug):
    d = Document.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        d.title = request.form["title"].strip()
        d.content = request.form.get("content","")
        new_slug = request.form.get("slug").strip() or slug
        if new_slug != d.slug and Document.query.filter_by(slug=new_slug).first():
            flash("슬러그가 이미 존재합니다.", "error")
            return redirect(url_for("edit_doc", slug=slug))
        d.slug = new_slug
        db.session.commit()
        log("edit_document", f"slug={d.slug}")
        return redirect(url_for("doc_view", slug=d.slug))
    return render_template("edit.html", d=d)

@app.route("/delete/<slug>", methods=["POST"])
def delete_doc(slug):
    d = Document.query.filter_by(slug=slug).first_or_404()
    db.session.delete(d)
    db.session.commit()
    log("delete_document", f"slug={slug}")
    flash("삭제되었습니다.", "ok")
    return redirect(url_for("index"))

# Auth
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["password"]
        agree_terms = request.form.get("agree_terms")
        agree_priv = request.form.get("agree_privacy")
        if not (agree_terms and agree_priv):
            flash("약관과 개인정보처리방침에 동의해야 가입할 수 있습니다.", "error")
            return redirect(url_for("signup"))
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "error")
            return redirect(url_for("signup"))
        pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt())
        u = User(email=email, password_hash=pw_hash)
        db.session.add(u)
        db.session.commit()
        log("signup", f"email={email}")
        flash("가입 완료! 로그인 해주세요.", "ok")
        return redirect(url_for("login"))
    terms = Document.query.filter_by(slug="terms").first()
    privacy = Document.query.filter_by(slug="privacy").first()
    return render_template("signup.html", terms=terms, privacy=privacy)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["password"]
        u = User.query.filter_by(email=email).first()
        if not u or not bcrypt.checkpw(pw.encode(), u.password_hash):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return redirect(url_for("login"))
        session["user_id"] = u.id
        log("login", f"email={email}")
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("로그아웃 되었습니다.", "ok")
    return redirect(url_for("index"))

@app.route("/delete-account", methods=["POST"])
def delete_account():
    uid = session.get("user_id")
    if not uid:
        abort(403)
    u = User.query.get(uid)
    db.session.delete(u)
    session.pop("user_id", None)
    db.session.commit()
    log("delete_account")
    flash("계정이 삭제되었습니다.", "ok")
    return redirect(url_for("index"))

@app.route("/logs")
def logs():
    rows = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("logs.html", rows=rows)

# Ensure essential pages
def ensure_system_pages():
    ensure_columns()
    defaults = {
        "terms": ("이용약관", "이용약관 내용입니다. 관리자만 수정하세요."),
        "privacy": ("개인정보처리방침", "개인정보처리방침 내용입니다. 관리자만 수정하세요."),
    }
    for slug, (title, content) in defaults.items():
        d = Document.query.filter_by(slug=slug).first()
        if not d:
            d = Document(title=title, content=content, slug=slug)
            db.session.add(d)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

with app.app_context():
    db.create_all()
    ensure_system_pages()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
