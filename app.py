
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, event, ForeignKey
from sqlalchemy.orm import relationship

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL env var is missing.")
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Page(db.Model):
    __tablename__ = "pages"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, unique=True)
    content = db.Column(db.Text, default="", nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("pages.id", ondelete="CASCADE"), nullable=True)
    parent = relationship("Page", remote_side=[id], backref="children", passive_deletes=True)
    is_root = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(20), nullable=False)  # CREATE / UPDATE / DELETE
    page_title = db.Column(db.String(200), nullable=False)
    client_ip = db.Column(db.String(64), nullable=True)
    at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

def client_ip():
    # X-Forwarded-For 고려
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr

@app.route("/healthz")
def healthz():
    try:
        db.session.execute(db.select(func.count(Page.id))).scalar_one()
        db_ok = True
    except Exception:
        db_ok = False
    return {"app":"ok", "db":"up" if db_ok else "down"}

@app.route("/")
def index():
    pages = Page.query.order_by(Page.title.asc()).all()
    roots = [p for p in pages if p.parent_id is None]
    latest = Page.query.order_by(Page.updated_at.desc()).first()
    return render_template("index.html", roots=roots, latest=latest)

@app.route("/logs")
def logs():
    items = AuditLog.query.order_by(AuditLog.at.desc()).limit(500).all()
    return render_template("logs.html", items=items)

@app.route("/page/<int:pid>")
def view_page(pid):
    page = Page.query.get_or_404(pid)
    return render_template("view.html", page=page)

@app.route("/page/<int:pid>/edit", methods=["GET","POST"])
def edit_page(pid):
    page = Page.query.get_or_404(pid)
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        if not title:
            flash("제목은 비어 있을 수 없습니다.", "error")
            return render_template("edit.html", page=page)
        # title unique
        existing = Page.query.filter(Page.title==title, Page.id!=page.id).first()
        if existing:
            flash("동일한 제목의 문서가 이미 있습니다.", "error")
            return render_template("edit.html", page=page)
        page.title = title
        page.content = content
        db.session.commit()
        db.session.add(AuditLog(action="UPDATE", page_title=page.title, client_ip=client_ip()))
        db.session.commit()
        return redirect(url_for("view_page", pid=page.id))
    return render_template("edit.html", page=page)

@app.route("/create", methods=["GET","POST"])
def create():
    parents = Page.query.order_by(Page.title.asc()).all()
    if request.method == "POST":
        mode = request.form.get("mode")  # root or child
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        parent_id = request.form.get("parent_id") or None

        if not title:
            flash("제목을 입력해주세요.", "error")
            return render_template("create.html", parents=parents)

        if Page.query.filter_by(title=title).first():
            flash("동일한 제목의 문서가 이미 있습니다.", "error")
            return render_template("create.html", parents=parents)

        if mode == "root":
            page = Page(title=title, content=content, parent_id=None, is_root=True)
        elif mode == "child":
            if not parent_id:
                flash("하위 문서를 만들 때는 상위 문서를 반드시 선택해야 합니다.", "error")
                return render_template("create.html", parents=parents)
            parent = Page.query.get(int(parent_id))
            if not parent:
                flash("선택한 상위 문서를 찾을 수 없습니다.", "error")
                return render_template("create.html", parents=parents)
            # 하위의 하위 금지
            if parent.parent_id is not None:
                flash("하위 문서의 하위 문서는 만들 수 없습니다.", "error")
                return render_template("create.html", parents=parents)
            page = Page(title=title, content=content, parent_id=parent.id, is_root=False)
        else:
            flash("모드를 선택해주세요.", "error")
            return render_template("create.html", parents=parents)

        db.session.add(page)
        db.session.commit()
        db.session.add(AuditLog(action="CREATE", page_title=page.title, client_ip=client_ip()))
        db.session.commit()
        return redirect(url_for("view_page", pid=page.id))

    return render_template("create.html", parents=parents)

@app.route("/page/<int:pid>/delete", methods=["GET","POST"])
def delete_page(pid):
    page = Page.query.get_or_404(pid)
    if request.method == "POST":
        title = page.title
        db.session.delete(page)  # 하위는 ON DELETE CASCADE
        db.session.commit()
        db.session.add(AuditLog(action="DELETE", page_title=title, client_ip=client_ip()))
        db.session.commit()
        flash("삭제되었습니다.", "success")
        return redirect(url_for("index"))
    return render_template("delete_confirm.html", page=page)

@app.template_filter("fmt")
def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# Init DB table if not exists
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
