
import os
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "pool_recycle": 300}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

db = SQLAlchemy(app)

class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, unique=True)
    content = db.Column(db.Text, nullable=False, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True, index=True)
    parent = db.relationship("Document", remote_side=[id], backref="children")
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def is_top(self) -> bool:
        return self.parent_id is None

class Log(db.Model):
    __tablename__ = "logs"
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(120), nullable=False)
    doc_id = db.Column(db.Integer, nullable=True)
    doc_title = db.Column(db.String(200), nullable=True)
    actor_ip = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

with app.app_context():
    db.create_all()

def client_ip():
    return (request.headers.get("X-Forwarded-For") or request.remote_addr or "unknown").split(",")[0].strip()

def add_log(action, doc):
    db.session.add(Log(action=action, doc_id=(doc.id if doc else None), doc_title=(doc.title if doc else None), actor_ip=client_ip()))
    db.session.commit()

@app.route("/")
def home():
    tops = Document.query.filter(Document.parent_id.is_(None)).order_by(func.lower(Document.title)).all()
    recents = Document.query.order_by(Document.updated_at.desc()).limit(20).all()
    return render_template("index.html", tops=tops, recents=recents)

@app.route("/doc/<int:doc_id>")
def view_doc(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return render_template("view.html", doc=doc)

@app.route("/new", methods=["GET", "POST"])
def create_doc():
    top_candidates = Document.query.filter(Document.parent_id.is_(None)).order_by(func.lower(Document.title)).all()
    if request.method == "POST":
        mode = request.form.get("mode")
        title = (request.form.get("title") or "").strip()
        content = request.form.get("content") or ""
        parent_id = request.form.get("parent_id") or ""

        if not title:
            flash("제목을 입력해 주세요.", "error")
            return render_template("create.html", mode=mode, top_candidates=top_candidates, title=title, content=content, parent_id=parent_id)

        if Document.query.filter(func.lower(Document.title) == func.lower(title)).first():
            flash("동일한 제목의 문서가 이미 있습니다.", "error")
            return render_template("create.html", mode=mode, top_candidates=top_candidates, title=title, content=content, parent_id=parent_id)

        parent = None
        if mode == "top":
            parent_id = None
        elif mode == "child":
            if not parent_id:
                flash("하위 문서를 만들 상위 문서를 선택해 주세요.", "error")
                return render_template("create.html", mode=mode, top_candidates=top_candidates, title=title, content=content, parent_id=parent_id)
            parent = Document.query.get(int(parent_id))
            if not parent:
                flash("선택한 상위 문서를 찾을 수 없습니다.", "error")
                return render_template("create.html", mode=mode, top_candidates=top_candidates, title=title, content=content, parent_id=parent_id)
            if not parent.is_top():
                flash("하위 문서의 하위 문서는 만들 수 없습니다.", "error")
                return render_template("create.html", mode=mode, top_candidates=top_candidates, title=title, content=content, parent_id=parent_id)
        else:
            flash("문서 종류를 선택해 주세요.", "error")
            return render_template("create.html", mode=mode, top_candidates=top_candidates, title=title, content=content, parent_id=parent_id)

        new_doc = Document(title=title, content=content, parent=parent)
        db.session.add(new_doc)
        db.session.commit()
        add_log("CREATE", new_doc)
        flash("문서를 만들었습니다.", "success")
        return redirect(url_for("view_doc", doc_id=new_doc.id))

    return render_template("create.html", top_candidates=top_candidates, mode="top")

@app.route("/edit/<int:doc_id>", methods=["GET", "POST"])
def edit_doc(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = request.form.get("content") or ""
        if not title:
            flash("제목을 입력해 주세요.", "error")
            return render_template("edit.html", doc=doc)
        exists = Document.query.filter(Document.id != doc.id, func.lower(Document.title) == func.lower(title)).first()
        if exists:
            flash("동일한 제목의 문서가 이미 있습니다.", "error")
            return render_template("edit.html", doc=doc)

        doc.title = title
        doc.content = content
        db.session.commit()
        add_log("UPDATE", doc)
        flash("수정했습니다.", "success")
        return redirect(url_for("view_doc", doc_id=doc.id))
    return render_template("edit.html", doc=doc)

@app.route("/delete/<int:doc_id>", methods=["GET", "POST"])
def delete_doc(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if request.method == "POST":
        if request.form.get("confirm") != "yes":
            flash("삭제가 취소되었습니다.", "error")
            return redirect(url_for("view_doc", doc_id=doc.id))

        for child in list(doc.children):
            add_log("DELETE", child)
            db.session.delete(child)
        add_log("DELETE", doc)
        db.session.delete(doc)
        db.session.commit()
        flash("문서를 삭제했습니다.", "success")
        return redirect(url_for("home"))
    return render_template("delete_confirm.html", doc=doc, child_count=len(doc.children))

@app.route("/logs")
def list_logs():
    q = Log.query.order_by(Log.created_at.desc()).limit(500).all()
    return render_template("logs.html", logs=q)

@app.route("/healthz")
def healthz():
    try:
        db.session.execute(text("SELECT 1"))
        db_ok = "ok"
    except Exception:
        db_ok = "down"
    return {"app": "ok", "db": db_ok}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
