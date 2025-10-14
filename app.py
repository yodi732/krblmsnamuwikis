\
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import text

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY","dev-secret")
db_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
# Render/Heroku layout compatibility
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://","postgresql://",1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login = LoginManager(app)
login.login_view = "login"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=True)
    author_email = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    actor = db.Column(db.String(255))
    action = db.Column(db.String(255))
    target = db.Column(db.String(255))

@login.user_loader
def load_user(user_id:int):
    return db.session.get(User, int(user_id))

def bootstrap():
    """Create tables and add missing columns if the DB already exists."""
    db.create_all()
    # Add columns if they do not exist (Postgres safe)
    with db.engine.begin() as conn:
        conn.execute(text('ALTER TABLE "document" ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NULL'))
        conn.execute(text('ALTER TABLE "document" ADD COLUMN IF NOT EXISTS parent_id INTEGER NULL'))
        # add FK if not present (ignore errors)
        try:
            conn.execute(text('ALTER TABLE "document" ADD CONSTRAINT document_parent_fk FOREIGN KEY(parent_id) REFERENCES "document"(id)'))
        except Exception:
            pass

@app.before_request
def _ensure_schema():
    # Run once per process
    if not getattr(app, "_bootstrapped", False):
        bootstrap()
        app._bootstrapped = True

# simple password hasher (not for production; replace with werkzeug.security in real apps)
import hashlib
def hash_pw(pw:str)->str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

@app.route("/")
def index():
    parents = Document.query.filter_by(parent_id=None).order_by(Document.created_at.desc()).all()
    children = Document.query.filter(Document.parent_id.isnot(None)).order_by(Document.created_at.desc()).all()
    # group children by parent
    children_map = {}
    for c in children:
        children_map.setdefault(c.parent_id, []).append(c)
    return render_template("index.html", parents=parents, children_map=children_map)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        password = request.form.get("password","")
        agree = request.form.get("agree")
        if not agree:
            flash("약관 동의가 필요합니다.","error")
            return redirect(url_for("register"))
        if not email or not password:
            flash("입력 누락","error"); return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.","error"); return redirect(url_for("register"))
        u = User(email=email, password_hash=hash_pw(password))
        db.session.add(u); db.session.commit()
        login_user(u)
        return redirect(url_for("index"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        pw = request.form.get("password","")
        row = db.session.execute(text('SELECT id, email, password_hash AS pw FROM "user" WHERE email=:email LIMIT 1'), {"email":email}).first()
        if not row or row.pw != hash_pw(pw):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.","error")
            return redirect(url_for("login"))
        user = db.session.get(User, row.id)
        login_user(user)
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

def _log(action, target):
    db.session.add(AuditLog(actor=(current_user.email if current_user.is_authenticated else "anon"),
                            action=action, target=target))
    db.session.commit()

@app.route("/create", methods=["GET","POST"])
@login_required
def create_document():
    parents = Document.query.filter_by(parent_id=None).order_by(Document.created_at.desc()).all()
    if request.method == "POST":
        kind = request.form.get("kind","parent")
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        parent_id = request.form.get("parent_id")
        parent = None
        if kind == "child":
            # must have a valid parent whose parent_id is NULL (only one level)
            if not parent_id:
                flash("상위 문서를 선택하세요.","error"); return redirect(url_for("create_document"))
            parent = db.session.get(Document, int(parent_id))
            if not parent or parent.parent_id is not None:
                flash("하위문서의 하위문서는 만들 수 없습니다.","error"); return redirect(url_for("create_document"))
        doc = Document(title=title, content=content, author_email=current_user.email,
                       parent_id=(parent.id if parent else None))
        db.session.add(doc); db.session.commit()
        _log("create_document", f"{doc.id}:{doc.title}")
        return redirect(url_for("index"))
    return render_template("create.html", parents=parents)

@app.route("/edit/<int:doc_id>", methods=["GET","POST"])
@login_required
def edit_document(doc_id:int):
    doc = db.session.get(Document, doc_id) or abort(404)
    if request.method == "POST":
        doc.title = request.form.get("title","").strip()
        doc.content = request.form.get("content","")
        doc.updated_at = datetime.utcnow()
        db.session.commit()
        _log("edit_document", f"{doc.id}:{doc.title}")
        return redirect(url_for("index"))
    return render_template("edit.html", doc=doc)

@app.route("/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete_document(doc_id:int):
    doc = db.session.get(Document, doc_id) or abort(404)
    # If parent, cascade delete children
    if doc.parent_id is None:
        childs = Document.query.filter_by(parent_id=doc.id).all()
        for c in childs:
            db.session.delete(c)
    db.session.delete(doc)
    db.session.commit()
    _log("delete_document", str(doc_id))
    return redirect(url_for("index"))

@app.route("/logs")
@login_required
def logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("logs.html", logs=logs)

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/delete-account")
@login_required
def delete_account():
    # remove user's docs too
    docs = Document.query.filter_by(author_email=current_user.email).all()
    for d in docs:
        # delete children first if parent
        if d.parent_id is None:
            for c in Document.query.filter_by(parent_id=d.id).all():
                db.session.delete(c)
        db.session.delete(d)
    uid = current_user.id
    logout_user()
    db.session.execute(text('DELETE FROM "user" WHERE id=:id'), {"id":uid})
    db.session.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
