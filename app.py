
from flask import Flask, render_template, request, redirect, url_for, session, g, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy import inspect
import os, datetime

def _normalize_db_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://") and "+psycopg" not in raw:
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_db_url(os.getenv("DATABASE_URL", "sqlite:///local.db"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.getenv("SECRET_KEY", "dev-key")

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

def safe_migrate(engine: Engine):
    insp = inspect(engine)
    with engine.begin() as conn:
        # document: rename body -> content if needed
        if "document" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("document")]
            if "content" not in cols and "body" in cols:
                conn.execute(text('ALTER TABLE document RENAME COLUMN body TO content'))
        # user: add is_admin if missing
        if "user" in insp.get_table_names():
            ucols = [c["name"] for c in insp.get_columns("user")]
            if "is_admin" not in ucols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE'))
        # create tables if they do not exist
        db.create_all()

@app.before_request
def load_user():
    g.user = None
    if session.get("user_id"):
        g.user = db.session.get(User, session["user_id"])
    g.now = datetime.datetime.utcnow()

@app.context_processor
def inject_now():
    return {"now": datetime.datetime.utcnow()}

@app.route("/")
def index():
    docs = Document.query.filter_by(is_system=False).order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.route("/document/<int:doc_id>")
def view_document(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    return render_template("document_view.html", doc=doc)

@app.route("/document/new", methods=["GET","POST"])
def create_document():
    if not g.user: return redirect(url_for("login"))
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        if not title or not content: return render_template("document_edit.html", doc=None, error="필수 항목")
        db.session.add(Document(title=title, content=content, is_system=False))
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("document_edit.html", doc=None)

@app.route("/document/<int:doc_id>/edit", methods=["GET","POST"])
def edit_document(doc_id):
    if not g.user: return redirect(url_for("login"))
    doc = db.session.get(Document, doc_id) or abort(404)
    if doc.is_system: abort(403)
    if request.method == "POST":
        doc.title = request.form.get("title","").strip()
        doc.content = request.form.get("content","").strip()
        db.session.commit()
        return redirect(url_for("view_document", doc_id=doc.id))
    return render_template("document_edit.html", doc=doc)

@app.route("/document/<int:doc_id>/delete")
def delete_document(doc_id):
    if not g.user: return redirect(url_for("login"))
    doc = db.session.get(Document, doc_id) or abort(404)
    if doc.is_system: abort(403)
    db.session.delete(doc)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        pw = request.form.get("password","")
        user = User.query.filter(db.func.lower(User.email)==email).first()
        if user and check_password_hash(user.password_hash, pw):
            session["user_id"] = user.id
            return redirect(url_for("index"))
        return render_template("login.html", error="이메일 또는 비밀번호가 올바르지 않습니다.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        pw = request.form.get("password","")
        agree = request.form.get("agree_terms")
        if not agree:
            return render_template("signup.html", error="약관 동의가 필요합니다.")
        if User.query.filter(db.func.lower(User.email)==email).first():
            return render_template("signup.html", error="이미 존재하는 이메일입니다.")
        user = User(email=email, password_hash=generate_password_hash(pw), is_admin=False)
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return redirect(url_for("index"))
    return render_template("signup.html")

@app.route("/legal/terms")
def terms():
    return render_template("legal_terms.html")

@app.route("/legal/privacy")
def privacy():
    return render_template("legal_privacy.html")

if __name__ == "__main__":
    with app.app_context():
        safe_migrate(db.engine)
    app.run(debug=True)
else:
    with app.app_context():
        safe_migrate(db.engine)
