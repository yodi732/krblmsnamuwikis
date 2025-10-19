import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app.db")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")

db = SQLAlchemy(app)

# -----------------------------
# Models
# -----------------------------
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    # pw_hash used by existing code/logs. We'll ensure this column exists (see bootstrap below).
    pw_hash = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, raw: str):
        self.pw_hash = generate_password_hash(raw, method="pbkdf2:sha256", salt_length=16)

    def check_password(self, raw: str) -> bool:
        try:
            return check_password_hash(self.pw_hash, raw)
        except Exception:
            return False

class Doc(db.Model):
    __tablename__ = "doc"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, unique=True)
    body = db.Column(db.Text, nullable=False, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("doc.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    parent = db.relationship("Doc", remote_side=[id], backref="children")

# -----------------------------
# Bootstrap (safe migrations)
# -----------------------------
with app.app_context():
    db.create_all()
    # Ensure user.pw_hash column exists even if legacy table created without it.
    try:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS pw_hash TEXT NOT NULL DEFAULT "";'))
        db.session.commit()
    except Exception:
        db.session.rollback()

# -----------------------------
# Helpers
# -----------------------------
ALLOWED_DOMAIN = "@bl-m.kr"

def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return db.session.get(User, uid)

def login_required():
    if not current_user():
        return redirect(url_for("login", next=request.path))

def normalize_email(email:str) -> str:
    return (email or "").strip().lower()

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def home():
    # Build a combined tree view (one level of children shown, grandchildren hidden)
    docs = Doc.query.order_by(Doc.title.asc()).all()
    by_parent = {}
    for d in docs:
        by_parent.setdefault(d.parent_id, []).append(d)
    items = by_parent.get(None, [])
    return render_template("home.html", items=items, by_parent=by_parent, me=current_user())

@app.route("/doc/<int:doc_id>")
def view_doc(doc_id):
    d = db.session.get(Doc, doc_id) or abort(404)
    children = Doc.query.filter_by(parent_id=doc_id).order_by(Doc.title.asc()).all()
    return render_template("doc.html", d=d, children=children, me=current_user())

@app.route("/create", methods=["GET","POST"])
def create():
    me = current_user()
    if not me:
        return redirect(url_for("login", next=request.path))
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        body = request.form.get("body") or ""
        parent_id = request.form.get("parent_id")
        parent = None
        if parent_id:
            parent = db.session.get(Doc, int(parent_id))
        # Prevent grandchild creation (child of child)
        if parent and parent.parent_id is not None:
            flash("하위문서의 하위문서는 만들 수 없습니다.", "error")
            return redirect(url_for("create"))
        if not title:
            flash("제목을 입력하세요.", "error")
        else:
            doc = Doc(title=title, body=body, parent_id=parent.id if parent else None)
            db.session.add(doc)
            db.session.commit()
            return redirect(url_for("view_doc", doc_id=doc.id))
    parents = Doc.query.filter_by(parent_id=None).order_by(Doc.title.asc()).all()
    return render_template("create.html", parents=parents, me=me)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        pw = request.form.get("password") or ""
        user = User.query.filter(func.lower(User.email)==email).first()
        if user and user.check_password(pw):
            session["uid"] = user.id
            nxt = request.args.get("next") or url_for("home")
            return redirect(nxt)
        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
    return render_template("login.html", me=current_user())

@app.route("/logout")
def logout():
    session.pop("uid", None)
    return redirect(url_for("home"))

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        pw = request.form.get("password") or ""
        agree_terms = request.form.get("agree_terms") == "on"
        agree_privacy = request.form.get("agree_privacy") == "on"
        if not email.endswith(ALLOWED_DOMAIN):
            flash("학교 이메일(@bl-m.kr)만 가입할 수 있습니다.", "error")
            return render_template("signup.html", me=current_user())
        if not (agree_terms and agree_privacy):
            flash("이용약관과 개인정보처리방침에 모두 동의해야 합니다.", "error")
            return render_template("signup.html", me=current_user())
        if len(pw) < 6:
            flash("비밀번호는 6자 이상이어야 합니다.", "error")
            return render_template("signup.html", me=current_user())
        u = User.query.filter(func.lower(User.email)==email).first()
        if u:
            flash("이미 가입된 이메일입니다.", "error")
        else:
            u = User(email=email)
            u.set_password(pw)
            db.session.add(u)
            db.session.commit()
            session["uid"] = u.id
            return redirect(url_for("home"))
    return render_template("signup.html", me=current_user())

@app.route("/delete_account", methods=["POST"])
def delete_account():
    me = current_user()
    if not me:
        abort(403)
    # 즉시 삭제 + 관련 로그는 법적 보관 필요시만 유지(정책 문구와 일치)
    db.session.delete(me)
    db.session.commit()
    session.pop("uid", None)
    flash("계정이 삭제되었습니다.", "success")
    return redirect(url_for("home"))

# Simple logs page (login required)
@app.route("/logs")
def logs():
    me = current_user()
    if not me:
        return redirect(url_for("login", next=request.path))
    last_docs = Doc.query.order_by(Doc.updated_at.desc()).limit(50).all()
    return render_template("logs.html", docs=last_docs, me=me)

# alias endpoint for legacy templates if any
app.add_url_rule("/create", endpoint="create_doc", view_func=create, methods=["GET","POST"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
