\
import os
import re
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")
    raw_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
    if raw_url.startswith("postgres://"):
        raw_url = raw_url.replace("postgres://", "postgresql+psycopg://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = raw_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        ensure_schema_and_seed()

    register_routes(app)
    return app

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), unique=True, nullable=False)
    content = db.Column(db.Text, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship("Document", remote_side=[id], backref="children")

class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), nullable=False, default="(anonymous)")
    action = db.Column(db.String(50), nullable=False) # create/update/delete
    doc_title = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db.session.get(User, uid)

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper

def ensure_schema_and_seed():
    """Create tables and ensure columns exist. Also seed demo admin-less DB; legal pages are not wiki docs."""
    db.create_all()

    # Ensure AuditLog.user_email column exists for older DBs
    insp = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='audit_log'")).fetchall() if db.engine.url.get_backend_name() == "postgresql" else []
    if insp and ("user_email",) not in insp:
        # Add column if missing
        db.session.execute(text("ALTER TABLE audit_log ADD COLUMN user_email VARCHAR(255) NOT NULL DEFAULT '(anonymous)'"))
        db.session.commit()

def register_routes(app: Flask):
    def _log_action(user_email: str, action: str, doc_title: str):
        log = AuditLog(user_email=user_email, action=action, doc_title=doc_title)
        db.session.add(log)
        db.session.commit()

    @app.route("/")
    def index():
        # top-level docs
        tops = Document.query.filter_by(parent_id=None).order_by(Document.updated_at.desc()).all()
        return render_template("index.html", tops=tops, cu=current_user())

    @app.route("/docs/<int:doc_id>")
    def doc_view(doc_id):
        doc = db.session.get(Document, doc_id)
        if not doc:
            abort(404)
        return render_template("doc_view.html", doc=doc, cu=current_user())

    @app.route("/docs/new", methods=["GET", "POST"])
    @login_required
    def doc_new():
        if request.method == "POST":
            title = (request.form.get("title") or "").strip()
            content = request.form.get("content") or ""
            parent_id = request.form.get("parent_id") or ""
            parent = None
            if parent_id:
                parent = db.session.get(Document, int(parent_id))
                if not parent or parent.parent_id is not None:
                    flash("하위의 하위 문서는 만들 수 없습니다.", "error")
                    return redirect(url_for("doc_new"))
            if not title:
                flash("제목을 입력하세요.", "error")
                return redirect(url_for("doc_new"))
            if Document.query.filter_by(title=title).first():
                flash("같은 제목의 문서가 이미 있습니다.", "error")
                return redirect(url_for("doc_new"))
            doc = Document(title=title, content=content, parent_id=parent.id if parent else None)
            db.session.add(doc)
            db.session.commit()
            _log_action(current_user().email, "create", title)
            return redirect(url_for("index"))
        # Parents = only top-level
        parents = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
        return render_template("doc_new.html", parents=parents, cu=current_user())

    @app.route("/docs/<int:doc_id>/edit", methods=["GET", "POST"])
    @login_required
    def doc_edit(doc_id):
        doc = db.session.get(Document, doc_id)
        if not doc:
            abort(404)
        if request.method == "POST":
            doc.content = request.form.get("content") or ""
            doc.updated_at = datetime.utcnow()
            db.session.commit()
            _log_action(current_user().email, "update", doc.title)
            return redirect(url_for("doc_view", doc_id=doc.id))
        return render_template("doc_edit.html", doc=doc, cu=current_user())

    @app.route("/docs/<int:doc_id>/delete", methods=["POST"])
    @login_required
    def doc_delete(doc_id):
        doc = db.session.get(Document, doc_id)
        if not doc:
            abort(404)
        title = doc.title
        # also delete children
        for c in list(doc.children):
            db.session.delete(c)
        db.session.delete(doc)
        db.session.commit()
        _log_action(current_user().email, "delete", title)
        return redirect(url_for("index"))

    @app.route("/logs")
    @login_required
    def view_logs():
        logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(500).all()
        return render_template("logs.html", logs=logs, cu=current_user())

    # Legal pages - not editable or deletable
    @app.route("/legal/terms")
    def legal_terms():
        return render_template("legal_terms.html", cu=current_user())

    @app.route("/legal/privacy")
    def legal_privacy():
        return render_template("legal_privacy.html", cu=current_user())

    # Auth
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            pw = request.form.get("password") or ""
            user = User.query.filter_by(email=email).first()
            if user and user.password_hash == _simple_hash(pw):
                session["uid"] = user.id
                return redirect(request.args.get("next") or url_for("index"))
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
        return render_template("login.html", cu=current_user())

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            pw = request.form.get("password") or ""
            pw2 = request.form.get("password2") or ""
            agree1 = request.form.get("agree_terms") == "on"
            agree2 = request.form.get("agree_privacy") == "on"
            if not (email and pw and pw2 and agree1 and agree2):
                flash("모든 필드를 채워주세요.", "error")
                return redirect(url_for("signup"))
            if pw != pw2:
                flash("비밀번호가 일치하지 않습니다.", "error")
                return redirect(url_for("signup"))
            if User.query.filter_by(email=email).first():
                flash("이미 가입된 이메일입니다.", "error")
                return redirect(url_for("signup"))
            user = User(email=email, password_hash=_simple_hash(pw))
            db.session.add(user)
            db.session.commit()
            session["uid"] = user.id
            return redirect(url_for("index"))
        return render_template("signup.html", cu=current_user())

    @app.route("/account/delete", methods=["POST"])
    @login_required
    def account_delete():
        u = current_user()
        # delete user's personal data (only email + hash stored)
        session.clear()
        db.session.delete(u)
        db.session.commit()
        return redirect(url_for("index"))

def _simple_hash(pw: str) -> str:
    # Lightweight hash to avoid bringing extra deps while keeping irreversible storage
    import hashlib
    return hashlib.sha256(("byeollae_salt__" + pw).encode()).hexdigest()

app = create_app()
