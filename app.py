from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from sqlalchemy import text
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY","dev-secret")

# Database config
db_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Models
class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # align with DB (no 'body')
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_system = db.Column(db.Boolean, default=False, nullable=False)

    parent = db.relationship("Document", remote_side=[id], backref="children")

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    pw_hash = db.Column(db.String(255), nullable=False)  # column name that logs expect
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

def ensure_schema_and_seed():
    # Create tables if missing
    db.create_all()

    # Ensure columns exist & compatible (Postgres-safe)
    with db.engine.begin() as conn:
        # document.content fix if an old 'body' exists
        # Add content if not exists
        conn.exec_driver_sql("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='document' AND column_name='content'
                ) THEN
                    ALTER TABLE document ADD COLUMN content TEXT NOT NULL DEFAULT '';
                END IF;
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='document' AND column_name='body'
                ) THEN
                    UPDATE document SET content = COALESCE(content, '') || COALESCE(body, '');
                    ALTER TABLE document DROP COLUMN body;
                END IF;
                -- is_system
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='document' AND column_name='is_system'
                ) THEN
                    ALTER TABLE document ADD COLUMN is_system BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
                -- updated_at
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='document' AND column_name='updated_at'
                ) THEN
                    ALTER TABLE document ADD COLUMN updated_at TIMESTAMP WITHOUT TIME ZONE;
                    UPDATE document SET updated_at = NOW() WHERE updated_at IS NULL;
                    ALTER TABLE document ALTER COLUMN updated_at SET DEFAULT NOW();
                END IF;
                -- user.pw_hash
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='"user"' AND column_name='pw_hash'
                ) THEN
                    ALTER TABLE "user" ADD COLUMN pw_hash VARCHAR(255) NOT NULL DEFAULT '';
                END IF;
            END$$;
        """)

        # Seed system docs
        conn.exec_driver_sql("""
            INSERT INTO document (title, content, parent_id, created_at, updated_at, is_system)
            SELECT '이용약관', '서비스 이용약관 본문입니다.', NULL, NOW(), NOW(), TRUE
            WHERE NOT EXISTS (SELECT 1 FROM document WHERE is_system = TRUE AND title = '이용약관');
        """)
        conn.exec_driver_sql("""
            INSERT INTO document (title, content, parent_id, created_at, updated_at, is_system)
            SELECT '개인정보처리방침', '개인정보처리방침 본문입니다.', NULL, NOW(), NOW(), TRUE
            WHERE NOT EXISTS (SELECT 1 FROM document WHERE is_system = TRUE AND title = '개인정보처리방침');
        """)

@app.before_request
def _run_once():
    # one-time init per worker
    if not getattr(app, "_inited", False):
        with app.app_context():
            ensure_schema_and_seed()
            app._inited = True

# Helpers
def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return User.query.get(uid)

def login_required():
    if not current_user():
        return redirect(url_for("login", next=request.path))

# Routes
@app.route("/")
def home():
    items = Document.query.order_by(Document.title.asc()).all()
    return render_template("home.html", items=items, me=current_user())

@app.route("/doc/<int:doc_id>")
def view_doc(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return render_template("view.html", doc=doc, me=current_user())

@app.route("/create", methods=["GET","POST"])
def create():
    if not current_user():
        return redirect(url_for("login", next=url_for("create")))
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        parent_id = request.form.get("parent_id")
        parent_id = int(parent_id) if parent_id else None
        # block depth > 1: allow only root or one level
        if parent_id:
            parent = Document.query.get(parent_id)
            if parent and parent.parent_id:
                flash("하위문서의 하위문서는 만들 수 없습니다.")
                return redirect(url_for("create"))
        doc = Document(title=title, content=content, parent_id=parent_id)
        db.session.add(doc)
        db.session.commit()
        return redirect(url_for("view_doc", doc_id=doc.id))
    roots = Document.query.filter(Document.parent_id.is_(None)).order_by(Document.title).all()
    return render_template("create.html", roots=roots, me=current_user())

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        user = User.query.filter_by(email=email).first()
        if not user or not user.pw_hash or not check_password_hash(user.pw_hash, password):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.")
            return render_template("login.html", me=current_user())
        session["uid"] = user.id
        nxt = request.args.get("next") or url_for("home")
        return redirect(nxt)
    return render_template("login.html", me=current_user())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        agree_terms = request.form.get("agree_terms") == "on"
        agree_priv = request.form.get("agree_priv") == "on"
        if not (agree_terms and agree_priv):
            flash("약관과 개인정보처리방침에 모두 동의해야 합니다.")
            return render_template("signup.html", me=current_user())
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.")
            return render_template("signup.html", me=current_user())
        u = User(email=email, pw_hash=generate_password_hash(password))
        db.session.add(u)
        db.session.commit()
        session["uid"] = u.id
        return redirect(url_for("home"))
    # Load doc ids for links
    terms = Document.query.filter_by(is_system=True, title="이용약관").first()
    priv = Document.query.filter_by(is_system=True, title="개인정보처리방침").first()
    return render_template("signup.html", terms=terms, priv=priv, me=current_user())

@app.route("/terms")
def terms():
    doc = Document.query.filter_by(is_system=True, title="이용약관").first()
    if not doc:
        abort(404)
    return redirect(url_for("view_doc", doc_id=doc.id))

@app.route("/privacy")
def privacy():
    doc = Document.query.filter_by(is_system=True, title="개인정보처리방침").first()
    if not doc:
        abort(404)
    return redirect(url_for("view_doc", doc_id=doc.id))

if __name__ == "__main__":
    app.run(debug=True)
