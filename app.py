
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "devkey")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ---------- Models ----------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Plain for demo; replace with hashing in prod
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, default="")
    author_email = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship("Document", remote_side=[id], backref="children")

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ---------- Helpers ----------
def top_level_docs():
    return Document.query.filter_by(parent_id=None).order_by(Document.updated_at.desc()).all()

@app.template_filter("dt")
def fmt_dt(value):
    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M")

# ---------- Routes ----------
@app.route("/")
def index():
    parents = top_level_docs()
    return render_template("index.html", parents=parents)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        pw = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.password == pw:
            login_user(user)
            return redirect(url_for("index"))
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        pw = request.form.get("password","")
        agree = request.form.get("agree") == "on"
        if not agree:
            flash("개인정보 처리방침과 이용약관에 동의해야 합니다.", "error")
            return render_template("register.html")
        if not email or not pw:
            flash("이메일과 비밀번호를 입력하세요.", "error")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "error")
            return render_template("register.html")
        user = User(email=email, password=pw)
        db.session.add(user)
        db.session.commit()
        flash("회원가입이 완료되었습니다. 로그인하세요.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("로그아웃되었습니다.", "success")
    return redirect(url_for("index"))

@app.route("/withdraw", methods=["POST"])
@login_required
def withdraw():
    # Delete user and their documents (optional).
    # Keep documents to avoid data loss for others. Here we just delete user.
    u = current_user
    logout_user()
    db.session.delete(User.query.get(u.id))
    db.session.commit()
    flash("회원탈퇴가 완료되었습니다.", "success")
    return redirect(url_for("index"))

@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    # Only allow child-of-parent, not grandchild
    parents = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
    if request.method == "POST":
        kind = request.form.get("kind")  # parent or child
        parent_id = request.form.get("parent_id")
        title = (request.form.get("title") or "").strip()
        body = request.form.get("body") or ""
        if not title:
            flash("제목을 입력하세요.", "error")
            return render_template("create.html", parents=parents)
        parent = None
        if kind == "child":
            if not parent_id:
                flash("상위 문서를 선택하세요.", "error")
                return render_template("create.html", parents=parents)
            parent = db.session.get(Document, int(parent_id))
            if not parent or parent.parent_id is not None:
                # Prevent creating a grandchild
                flash("하위문서의 하위문서는 만들 수 없습니다.", "error")
                return render_template("create.html", parents=parents)
        doc = Document(title=title, body=body, author_email=current_user.email, parent=parent)
        db.session.add(doc)
        db.session.commit()
        flash("문서가 저장되었습니다.", "success")
        return redirect(url_for("index"))
    return render_template("create.html", parents=parents)

@app.route("/edit/<int:doc_id>", methods=["GET", "POST"])
@login_required
def edit_document(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    if request.method == "POST":
        doc.title = (request.form.get("title") or "").strip()
        doc.body = request.form.get("body") or ""
        db.session.commit()
        flash("수정되었습니다.", "success")
        return redirect(url_for("index"))
    parents = Document.query.filter_by(parent_id=None).all()
    return render_template("edit.html", doc=doc, parents=parents)

@app.route("/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete_document(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    # Allow delete only if no children exist
    if doc.children:
        for c in doc.children:
            db.session.delete(c)
    db.session.delete(doc)
    db.session.commit()
    flash("삭제되었습니다.", "success")
    return redirect(url_for("index"))

# View route (if needed by links)
@app.route("/view/<int:doc_id>")
def view_document(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    return render_template("view.html", doc=doc)

# ---------- CLI ----------
@app.cli.command("init-db")
def init_db():
    db.create_all()
    if not User.query.filter_by(email="admin@school.kr").first():
        db.session.add(User(email="admin@school.kr", password="admin"))
        db.session.commit()
    print("DB initialized.")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email="admin@school.kr").first():
            db.session.add(User(email="admin@school.kr", password="admin"))
            db.session.commit()
    app.run(host="0.0.0.0", port=5000, debug=True)
