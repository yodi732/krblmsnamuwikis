
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

# --- App & Config ---
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///local.db")
# Render의 DATABASE_URL이 postgres:// 로 시작할 수 있으므로 sqlalchemy가 인식하도록 조정
uri = app.config["SQLALCHEMY_DATABASE_URI"]
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
if uri.startswith("postgresql://") and "+psycopg" not in uri:
    uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = uri

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
LOG_ANONYMIZE_IP = os.environ.get("LOG_ANONYMIZE_IP", "true").lower() == "true"

db = SQLAlchemy(app)

from sqlalchemy import text, inspect

def ensure_schema():
    insp = inspect(db.engine)
    if insp.has_table("document"):
        cols = {c["name"] for c in insp.get_columns("document")}
        with db.engine.begin() as conn:
            if "created_at" not in cols:
                conn.execute(text("ALTER TABLE document ADD COLUMN created_at TIMESTAMPTZ DEFAULT now() NOT NULL"))
            if "parent_id" not in cols:
                conn.execute(text("ALTER TABLE document ADD COLUMN parent_id INTEGER NULL"))
                try:
                    conn.execute(text("ALTER TABLE document ADD CONSTRAINT document_parent_fk FOREIGN KEY (parent_id) REFERENCES document(id) ON DELETE CASCADE"))
                except Exception:
                    pass
    else:
        db.create_all()

with app.app_context():
    db.create_all()
    ensure_schema()

# --- Models ---
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parent_id = db.Column(db.Integer, db.ForeignKey('document.id', ondelete='CASCADE'), nullable=True)
    children = db.relationship(
        'Document',
        cascade='all, delete-orphan',
        backref=db.backref('parent', remote_side='Document.id'),
        lazy='select'
    )

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(20), nullable=False)  # CREATE / DELETE
    doc_id = db.Column(db.Integer, nullable=False)
    ip = db.Column(db.String(255), nullable=True)

def mask_ip(ip):
    if not ip:
        return ""
    parts = [p.strip() for p in ip.split(",")]
    masked = []
    for p in parts:
        if ":" in p:  # IPv6
            segs = p.split(":")
            if len(segs) > 2:
                segs[-1] = "****"
            masked.append(":".join(segs))
        elif "." in p:  # IPv4
            segs = p.split(".")
            if len(segs) == 4:
                segs[-1] = "***"
            masked.append(".".join(segs))
        else:
            masked.append(p)
    return ", ".join(masked)

# Flask 3에서는 before_first_request가 제거됨 → 앱 로드 시 컨텍스트에서 테이블 생성
with app.app_context():
    db.create_all()

# --- Routes ---

@app.route("/")
def index():
    try:
        parents = (Document.query
                   .filter_by(parent_id=None)
                   .order_by(Document.created_at.desc())
                   .all())
    except Exception:
        parents = (Document.query
                   .filter_by(parent_id=None)
                   .order_by(Document.id.desc())
                   .all())
    return render_template("index.html", parents=parents)

@app.route("/create", methods=["GET", "POST"])
def create_document():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = request.form.get("content") or ""
        doc_type = request.form.get("doc_type", "parent")
        parent_id = request.form.get("parent_id")

        if not title:
            flash("제목을 입력하세요.", "warning")
            return redirect(url_for("create_document"))

        parent = None
        if doc_type == "child":
            if not parent_id:
                flash("하위 문서의 상위 문서를 선택하세요.", "warning")
                return redirect(url_for("create_document"))
            parent = Document.query.get_or_404(int(parent_id))
            if parent.parent_id is not None:
                flash("하위 문서의 하위 문서는 만들 수 없습니다.", "danger")
                return redirect(url_for("create_document"))

        doc = Document(title=title, content=content, parent=parent)
        db.session.add(doc)
        db.session.commit()

        # 로그
        ip_chain = request.headers.get("X-Forwarded-For", request.remote_addr)
        db.session.add(Log(action="CREATE", doc_id=doc.id, ip=mask_ip(ip_chain) if LOG_ANONYMIZE_IP else ip_chain))
        db.session.commit()

        return redirect(url_for("create_document"))

    parents = (Document.query
               .filter_by(parent_id=None)
               .order_by(Document.created_at.desc())
               .all())
    return render_template("create.html", parents=parents)

@app.post("/delete/<int:doc_id>")
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    db.session.delete(doc)
    db.session.commit()

    ip_chain = request.headers.get("X-Forwarded-For", request.remote_addr)
    db.session.add(Log(action="DELETE", doc_id=doc_id, ip=mask_ip(ip_chain) if LOG_ANONYMIZE_IP else ip_chain))
    db.session.commit()

    return redirect(request.referrer or url_for("index"))

@app.route("/logs")
def view_logs():
    logs = Log.query.order_by(Log.time.desc()).limit(500).all()
    return render_template("logs.html", logs=logs)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
