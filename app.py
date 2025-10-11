
import os
from datetime import datetime
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy

def _coerce_sqlalchemy_url(url: str) -> str:
    '''Convert postgres:// to postgresql+psycopg:// for SQLAlchemy 2.x'''
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        # explicitly use psycopg driver if not specified
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
# DB
db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URI")
if not db_url:
    raise RuntimeError("DATABASE_URL (or DATABASE_URI) env var is required")
app.config["SQLALCHEMY_DATABASE_URI"] = _coerce_sqlalchemy_url(db_url)
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Logging privacy (mask IPs by default)
app.config["LOG_ANONYMIZE_IP"] = os.environ.get("LOG_ANONYMIZE_IP", "true").lower() not in ("0","false","no")

db = SQLAlchemy(app)

class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship("Document", remote_side=[id], backref=db.backref("children", cascade="all, delete-orphan"))

class ActionLog(db.Model):
    __tablename__ = "action_logs"
    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    action = db.Column(db.String(32), nullable=False)  # CREATE/UPDATE/DELETE
    doc_title = db.Column(db.String(255), nullable=False)
    ip = db.Column(db.String(80), nullable=True)  # anonymized/masked

def mask_ip(ip: str) -> str:
    try:
        import ipaddress
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.version == 4:
            parts = ip.split(".")
            parts[-1] = "0"
            return ".".join(parts)
        else:
            hextets = ip.split(":")
            return ":".join(hextets[:4]) + "::"
    except Exception:
        return ip

@app.before_first_request
def init_db():
    db.create_all()

def log_action(action: str, title: str):
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "-"
    if app.config["LOG_ANONYMIZE_IP"]:
        ip = mask_ip(ip)
    db.session.add(ActionLog(action=action, doc_title=title, ip=ip))
    db.session.commit()

@app.route("/")
def index():
    tops = Document.query.filter_by(parent_id=None).order_by(Document.created_at.asc()).all()
    return render_template("index.html", tops=tops)

@app.route("/doc/<int:doc_id>")
def view_doc(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return render_template("doc.html", doc=doc)

@app.route("/create", methods=["GET","POST"])
def create():
    tops = Document.query.filter_by(parent_id=None).order_by(Document.created_at.asc()).all()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = request.form.get("content") or ""
        kind = request.form.get("kind")  # 'top' or 'child'
        parent_choice = request.form.get("parent_id")  # may be ""
        if not title:
            flash("제목을 입력하세요.", "danger")
            return render_template("create.html", tops=tops)
        parent_id = None
        if kind == "child":
            if not parent_choice:
                flash("상위 문서를 선택하세요.", "danger")
                return render_template("create.html", tops=tops)
            parent_id = int(parent_choice)
            parent = Document.query.get(parent_id)
            if parent is None or parent.parent_id is not None:
                flash("하위 문서는 오직 상위 문서의 바로 아래만 가능합니다.", "danger")
                return render_template("create.html", tops=tops)
        doc = Document(title=title, content=content, parent_id=parent_id)
        db.session.add(doc)
        db.session.commit()
        log_action("CREATE", title)
        return redirect(url_for("view_doc", doc_id=doc.id))
    return render_template("create.html", tops=tops)

@app.route("/edit/<int:doc_id>", methods=["GET","POST"])
def edit(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if request.method == "POST":
        doc.title = (request.form.get("title") or doc.title).strip()
        doc.content = request.form.get("content") or ""
        db.session.commit()
        log_action("UPDATE", doc.title)
        flash("수정 완료!", "success")
        return redirect(url_for("view_doc", doc_id=doc.id))
    return render_template("edit.html", doc=doc)

@app.route("/delete/<int:doc_id>", methods=["POST"])
def delete(doc_id):
    doc = Document.query.get_or_404(doc_id)
    title = doc.title
    db.session.delete(doc)
    db.session.commit()
    log_action("DELETE", title)
    flash("삭제되었습니다.", "success")
    return redirect(url_for("index"))

@app.route("/logs")
def logs():
    items = ActionLog.query.order_by(ActionLog.ts.desc()).limit(500).all()
    return render_template("logs.html", items=items, ip_private=app.config["LOG_ANONYMIZE_IP"])

@app.route("/healthz")
def health():
    ok = True
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        ok = False
    return {"app":"ok", "db":"up" if ok else "down"}
