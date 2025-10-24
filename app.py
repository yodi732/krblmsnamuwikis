from flask import Flask, render_template, request, redirect, url_for, session, g, abort, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text, inspect
import os, datetime, json
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///local.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.getenv("SECRET_KEY", "dev-key")

KST = timezone(timedelta(hours=9))

@app.context_processor
def inject_now():
    # footer에서 {{ now.year }} 쓰기 위함
    return {"now": datetime.now(KST)}

db = SQLAlchemy(app)

db = SQLAlchemy(app)

# ── Models ─────────────────────────────────────────────────────────────────────
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
    # parent-child
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True, index=True)
    parent = db.relationship("Document", remote_side=[id], backref=db.backref("children", lazy="dynamic"))

# ── Safe migrate ───────────────────────────────────────────────────────────────
def safe_migrate():
    insp = inspect(db.engine)
    with db.engine.begin() as conn:
        # document.body → content
        if "document" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("document")]
            if "content" not in cols and "body" in cols:
                conn.execute(text("ALTER TABLE document RENAME COLUMN body TO content"))
        # user.is_admin 없으면 추가
        if "user" in insp.get_table_names():
            ucols = [c["name"] for c in insp.get_columns("user")]
            if "is_admin" not in ucols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE'))
        # parent_id 없으면 추가
        if "document" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("document")]
            if "parent_id" not in cols:
                try:
                    conn.execute(text('ALTER TABLE "document" ADD COLUMN parent_id INTEGER'))
                except Exception:
                    pass
    db.create_all()

# ── Audit log ──────────────────────────────────────────────────────────────────
AUDIT_LOG = os.path.join(os.path.dirname(__file__), "audit.log")

def write_audit(action, user_email, doc_id=None, title=None):
    try:
        rec = {
            "ts": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "user": user_email,
            "action": action,  # create/update/delete
            "doc_id": doc_id,
            "title": title,
        }
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\\n")
    except Exception:
        pass

# ── Request hooks ──────────────────────────────────────────────────────────────
@app.before_request
def load_user():
    g.user = None
    uid = session.get("user_id")
    if uid:
        g.user = db.session.get(User, uid)

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    # 최신 문서 리스트
    docs = Document.query.filter_by(is_system=False).order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.route("/home")
def home():
    # 상위/하위 구조 트리 뷰
    roots = Document.query.filter_by(parent_id=None, is_system=False).order_by(Document.created_at.desc()).all()
    return render_template("home.html", roots=roots)

@app.route("/document/<int:doc_id>")
def view_document(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    children = doc.children.order_by(Document.created_at.desc()).all()
    return render_template("document_view.html", doc=doc, children=children)

@app.route("/document/new", methods=["GET", "POST"])
def create_document():
    if not g.user:
        return redirect(url_for("login"))
    parent_id = request.args.get("parent_id", type=int)
    parent = db.session.get(Document, parent_id) if parent_id else None

    if request.method == "POST":
        mode = request.form.get("mode")  # parent or child
        selected_parent_id = request.form.get("parent_id", type=int)
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        if not title or not content:
            return render_template("document_edit.html", doc=None, parent=parent, mode=mode, parents=_parent_choices(), error="제목/내용은 필수입니다.")

        pid = None
        if mode == "child":
            pid = selected_parent_id or (parent.id if parent else None)

        doc = Document(title=title, content=content, is_system=False, parent_id=pid)
        db.session.add(doc)
        db.session.commit()
        write_audit("create", g.user.email, doc_id=doc.id, title=doc.title)
        return redirect(url_for("view_document", doc_id=doc.id))
    return render_template("document_edit.html", doc=None, parent=parent, mode=("child" if parent else "parent"), parents=_parent_choices())

def _parent_choices():
    return Document.query.filter_by(is_system=False).order_by(Document.created_at.desc()).all()

@app.route("/document/<int:doc_id>/edit", methods=["GET", "POST"])
def edit_document(doc_id):
    if not g.user:
        return redirect(url_for("login"))
    doc = db.session.get(Document, doc_id) or abort(404)
    if doc.is_system:
        abort(403)
    if request.method == "POST":
        doc.title = request.form.get("title", "").strip()
        doc.content = request.form.get("content", "").strip()
        # 재배치 (선택적)
        mode = request.form.get("mode")
        selected_parent_id = request.form.get("parent_id", type=int)
        if mode == "parent":
            doc.parent_id = None
        elif mode == "child":
            doc.parent_id = selected_parent_id if selected_parent_id else None
        db.session.commit()
        write_audit("update", g.user.email, doc_id=doc.id, title=doc.title)
        return redirect(url_for("view_document", doc_id=doc.id))
    return render_template("document_edit.html", doc=doc, parent=doc.parent, mode=("child" if doc.parent_id else "parent"), parents=_parent_choices())

@app.post("/document/<int:doc_id>/delete")
def delete_document(doc_id):
    if not g.user:
        abort(403)
    doc = db.session.get(Document, doc_id) or abort(404)
    if doc.is_system:
        flash("시스템 문서는 삭제할 수 없습니다.", "warning")
        return redirect(url_for("index"))
    title = doc.title
    # 하위 문서까지 일괄 삭제
    def delete_subtree(d):
        for c in d.children.all():
            delete_subtree(c)
        db.session.delete(d)
    delete_subtree(doc)
    db.session.commit()
    write_audit("delete", g.user.email, doc_id=doc.id, title=title)
    flash("문서를 삭제했습니다.", "success")
    return redirect(url_for("index"))

@app.get("/logs")
def logs():
    if not g.user:
        abort(403)
    rows = []
    if os.path.exists(AUDIT_LOG):
        with open(AUDIT_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except:
                    pass
    rows.reverse()
    return render_template("logs.html", rows=rows)

# ── Auth ───────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and check_password_hash(user.password_hash, pw):
            session["user_id"] = user.id
            return redirect(url_for("index"))
        return render_template("login.html", error="이메일 또는 비밀번호가 올바르지 않습니다.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        pw2 = request.form.get("password2", "")
        agree = request.form.get("agree_terms")

        if not agree:
            return render_template("signup.html", error="약관에 동의해 주세요.")
        if not email.endswith("@bl-m.kr"):
            return render_template("signup.html", error="학교 계정(@bl-m.kr)만 가입 가능합니다.")
        if pw != pw2:
            return render_template("signup.html", error="비밀번호가 일치하지 않습니다.")
        if User.query.filter(db.func.lower(User.email) == email).first():
            return render_template("signup.html", error="이미 가입된 이메일입니다.")

        user = User(email=email, password_hash=generate_password_hash(pw), is_admin=False)
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return redirect(url_for("index"))
    return render_template("signup.html")

@app.route("/account/delete", methods=["GET","POST"])
def account_delete():
    if not g.user:
        return redirect(url_for("login"))
    if request.method == "POST":
        pw = request.form.get("password","")
        if not check_password_hash(g.user.password_hash, pw):
            return render_template("account_delete.html", error="비밀번호가 일치하지 않습니다.")
        # 사용자 삭제 (문서는 남기되 소유자 개념이 없으므로 그대로 둠)
        u = g.user
        session.clear()
        db.session.delete(u)
        db.session.commit()
        flash("회원 탈퇴가 완료되었습니다.", "success")
        return redirect(url_for("index"))
    return render_template("account_delete.html")

@app.route("/legal/terms")
def terms():
    return render_template("legal_terms.html")

@app.route("/legal/privacy")
def privacy():
    return render_template("legal_privacy.html")

# ── Boot ───────────────────────────────────────────────────────────────────────
with app.app_context():
    safe_migrate()

if __name__ == "__main__":
    app.run(debug=True)
