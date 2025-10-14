
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# --- DB (SQLite persistent file) ---
DB_PATH = os.environ.get("DATABASE_URL", "sqlite:///app.db")
app.config["SQLALCHEMY_DATABASE_URI"] = DB_PATH
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # plain for demo

    def get_id(self):
        return str(self.id)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, default="")
    author_email = db.Column(db.String(255))
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    parent = db.relationship("Document", remote_side=[id], backref="children")

# --- Ensure DB schema exists even under gunicorn ---
with app.app_context():
    db.create_all()
    # seed admin (optional)
    if not User.query.filter_by(email="admin@school.kr").first():
        db.session.add(User(email="admin@school.kr", password="admin"))
        db.session.commit()

@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))

# --- Helpers ---
def top_level_docs():
    return Document.query.filter_by(parent_id=None).order_by(Document.updated_at.desc()).all()

# --- Routes ---
@app.route("/")
def index():
    parents = top_level_docs()
    return render_template("index.html", parents=parents)

@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    doc_type = request.form.get("doc_type", "child")
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "")
        parent_id = request.form.get("parent_id")
        parent = None
        if parent_id:
            parent = db.session.get(Document, int(parent_id))
            # prevent child-of-child depth > 1
            if parent and parent.parent_id is not None:
                flash("하위문서의 하위문서는 만들 수 없습니다")
                return redirect(url_for("create"))
        if not title:
            flash("제목을 입력하세요")
            return redirect(url_for("create"))
        doc = Document(title=title, body=body, author_email=current_user.email, parent=parent)
        db.session.add(doc)
        db.session.commit()
        flash("문서를 저장했습니다")
        return redirect(url_for("index"))
    parents = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
    return render_template("create.html", parents=parents)

@app.route("/doc/<int:doc_id>")
def view_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        flash("존재하지 않는 문서입니다")
        return redirect(url_for("index"))
    return render_template("view.html", doc=doc)

@app.route("/edit/<int:doc_id>", methods=["GET", "POST"])
@login_required
def edit_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        flash("존재하지 않는 문서입니다")
        return redirect(url_for("index"))
    if request.method == "POST":
        doc.title = request.form.get("title", doc.title)
        doc.body = request.form.get("body", doc.body)
        db.session.commit()
        flash("수정했습니다")
        return redirect(url_for("view_document", doc_id=doc.id))
    return render_template("edit.html", doc=doc)

@app.route("/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc:
        db.session.delete(doc)
        db.session.commit()
        flash("삭제했습니다")
    return redirect(url_for("index"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        pw = request.form.get("password","")
        user = User.query.filter_by(email=email, password=pw).first()
        if user:
            login_user(user)
            return redirect(url_for("index"))
        flash("로그인 실패")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        pw = request.form.get("password","")
        agree = request.form.get("agree")
        if not agree:
            flash("약관에 동의해야 합니다")
            return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("이미 존재하는 이메일입니다")
            return redirect(url_for("register"))
        user = User(email=email, password=pw)
        db.session.add(user)
        db.session.commit()
        flash("회원가입 완료. 로그인하세요")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("로그아웃 되었습니다")
    return redirect(url_for("index"))

@app.route("/withdraw", methods=["POST"])
@login_required
def withdraw():
    # delete current user and their docs
    email = current_user.email
    # optional: reassign docs? here we keep docs but clear author
    for d in Document.query.filter_by(author_email=email).all():
        d.author_email = "(탈퇴한 사용자)"
    user = db.session.get(User, current_user.id)
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash("회원탈퇴가 완료되었습니다")
    return redirect(url_for("index"))

# simple CLI (still usable locally)
@app.cli.command("init-db")
def init_db_cmd():
    """Initialize database tables and seed admin user"""
    db.create_all()
    if not User.query.filter_by(email="admin@school.kr").first():
        db.session.add(User(email="admin@school.kr", password="admin"))
        db.session.commit()
    print("DB initialized")

# --- Run (for local dev) ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
