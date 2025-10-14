\
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import text, event
from werkzeug.security import generate_password_hash, check_password_hash

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY","dev-secret")
    db_url = os.environ.get("DATABASE_URL")
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://","postgresql://",1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url or "sqlite:///app.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    return app

app = create_app()
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# -------------------- Models --------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    author_email = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)

    parent = db.relationship('Document', remote_side=[id], backref='children')

# -------------------- Bootstrap DB (schema guard) --------------------
def bootstrap_db():
    db.create_all()

    # Ensure audit_log exists and columns present
    db.session.execute(text("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id BIGSERIAL PRIMARY KEY,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        actor VARCHAR NOT NULL,
        action VARCHAR NOT NULL,
        target VARCHAR NOT NULL
    );"""))
    # Add columns if missing (idempotent)
    db.session.execute(text("""
    ALTER TABLE audit_log
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        ADD COLUMN IF NOT EXISTS actor VARCHAR,
        ADD COLUMN IF NOT EXISTS action VARCHAR,
        ADD COLUMN IF NOT EXISTS target VARCHAR;
    """))

    # Add updated_at to document if missing
    try:
        db.session.execute(text("ALTER TABLE document ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;"))
        db.session.execute(text("UPDATE document SET updated_at = COALESCE(updated_at, created_at);"))
        db.session.execute(text("ALTER TABLE document ALTER COLUMN updated_at SET NOT NULL;"))
    except Exception:
        db.session.rollback()

    db.session.commit()

# auto update timestamp
@event.listens_for(Document, "before_update")
def _before_update(mapper, connection, target):
    target.updated_at = datetime.utcnow()

# -------------------- Auth --------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        password = request.form.get("password","")
        agree = request.form.get("agree") == "on"
        if not email or not password:
            flash("이메일과 비밀번호를 입력하세요.", "error")
        elif not agree:
            flash("약관에 동의해야 합니다.", "error")
        elif db.session.execute(text('SELECT 1 FROM "user" WHERE email=:e'), {"e": email}).first():
            flash("이미 가입된 이메일입니다.", "error")
        else:
            u = User(email=email)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            login_user(u)
            _log("register", email)
            return redirect(url_for("index"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        password = request.form.get("password","")
        user = db.session.execute(text('SELECT id, email, password_hash FROM "user" WHERE email=:e LIMIT 1'), {"e": email}).first()
        if user:
            u = db.session.get(User, user.id)
            if u and u.check_password(password):
                login_user(u)
                _log("login", email)
                return redirect(url_for("index"))
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    _log("logout", current_user.email)
    logout_user()
    return redirect(url_for("index"))

@app.route("/delete_account", methods=["POST"])
@login_required
def delete_account():
    email = current_user.email
    # 삭제 전에 문서도 정리(작성자 본인 것만)
    db.session.execute(text("DELETE FROM document WHERE author_email = :e"), {"e": email})
    u = db.session.get(User, current_user.id)
    logout_user()
    db.session.delete(u)
    db.session.commit()
    _log("delete_account", email)
    flash("회원탈퇴가 완료되었습니다.", "info")
    return redirect(url_for("index"))

# -------------------- Logging helper --------------------
def _log(action: str, target: str):
    try:
        db.session.execute(text("""
            INSERT INTO audit_log (created_at, actor, action, target)
            VALUES (:ts, :actor, :action, :target)
        """), {
            "ts": datetime.utcnow(),
            "actor": (current_user.email if current_user.is_authenticated else "(anonymous)"),
            "action": action,
            "target": target
        })
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Audit log failed: %s", e)

# -------------------- Views --------------------
@app.route("/")
def index():
    # 상위문서 먼저, 그 아래 하위문서는 들여쓰기 표시
    parents = Document.query.filter_by(parent_id=None).order_by(Document.created_at.desc()).all()
    return render_template("index.html", parents=parents)

@app.route("/create", methods=["GET","POST"])
@login_required
def create_document():
    parents = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
    if request.method == "POST":
        mode = request.form.get("mode")  # "parent" or "child"
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        if not title:
            flash("제목을 입력하세요.", "error")
            return render_template("create.html", parents=parents)
        doc = Document(title=title, content=content, author_email=current_user.email)

        if mode == "child":
            parent_id = request.form.get("parent_id")
            if not parent_id:
                flash("상위 문서를 선택하세요.", "error")
                return render_template("create.html", parents=parents)
            parent = db.session.get(Document, int(parent_id))
            if not parent or parent.parent_id is not None:
                flash("하위의 하위문서는 만들 수 없습니다.", "error")
                return render_template("create.html", parents=parents)
            doc.parent_id = parent.id

        db.session.add(doc)
        db.session.commit()
        _log("create_document", doc.title)
        return redirect(url_for("index"))
    return render_template("create.html", parents=parents)

@app.route("/edit/<int:doc_id>", methods=["GET","POST"])
@login_required
def edit_document(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    if request.method == "POST":
        doc.title = request.form.get("title","").strip()
        doc.content = request.form.get("content","")
        db.session.commit()
        _log("update_document", doc.title)
        return redirect(url_for("index"))
    return render_template("edit.html", doc=doc)

@app.route("/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete_document(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    title = doc.title
    # 함께 딸린 하위문서도 제거
    for c in list(doc.children):
        db.session.delete(c)
    db.session.delete(doc)
    db.session.commit()
    _log("delete_document", title)
    return redirect(url_for("index"))

@app.route("/logs")
@login_required
def logs():
    rows = db.session.execute(text("""
        SELECT created_at, actor, action, target
        FROM audit_log
        ORDER BY id DESC
        LIMIT 500
    """)).mappings().all()
    return render_template("logs.html", logs=rows)

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

# -------------------- Templates: served by files --------------------

with app.app_context():
    bootstrap_db()

if __name__ == "__main__":
    app.run(debug=True)
