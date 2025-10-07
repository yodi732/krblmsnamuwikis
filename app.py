
import os
from datetime import datetime
from urllib.parse import quote_plus
from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy

def create_app():
    app = Flask(__name__)

    # DB URL (Render/Supabase) — must be postgresql+psycopg://...; fallback to sqlite for local dev
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if db_url and db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if not db_url:
        db_url = "sqlite:///local.db"

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db = SQLAlchemy(app)

    class Document(db.Model):
        __tablename__ = "documents"
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(255), nullable=False, unique=True)
        content = db.Column(db.Text, default="")
        parent_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

        parent = db.relationship("Document", remote_side=[id], backref="children")

        @property
        def is_root(self):
            return self.parent_id is None

    class Log(db.Model):
        __tablename__ = "logs"
        id = db.Column(db.Integer, primary_key=True)
        action = db.Column(db.String(50), nullable=False)
        doc_id = db.Column(db.Integer, nullable=False)
        doc_title = db.Column(db.String(255), nullable=False)
        author = db.Column(db.String(100))
        reason = db.Column(db.String(255))
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Create tables at boot
    with app.app_context():
        db.create_all()

    def _ctx():
        tocs = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
        children_map = {t.id: Document.query.filter_by(parent_id=t.id).order_by(Document.title.asc()).all() for t in tocs}
        return dict(tocs=tocs, children_map=children_map)

    @app.route("/")
    def home():
        docs = Document.query.order_by(Document.updated_at.desc()).all()
        return render_template("index.html", docs=docs, **_ctx())

    @app.route("/doc/<int:doc_id>")
    def view_document(doc_id):
        d = Document.query.get_or_404(doc_id)
        children = Document.query.filter_by(parent_id=doc_id).all()
        warning = None
        # Disallow going deeper than one level (no grandchildren)
        if d.parent_id is not None:
            # d is a child; don't allow its children to be created
            pass
        return render_template("document.html", doc=d, children=children, warning=warning, **_ctx())

    @app.route("/new", methods=["GET", "POST"])
    def new_document():
        parent_id = request.args.get("parent_id", type=int)
        form = {"title":"", "content":"", "author":"", "parent_id": parent_id}
        error = None
        if request.method == "POST":
            title = request.form.get("title","").strip()
            content = request.form.get("content","")
            author = request.form.get("author","").strip()
            sel_parent_id = request.form.get("parent_id") or None
            if sel_parent_id:
                sel_parent_id = int(sel_parent_id)
                parent = Document.query.get(sel_parent_id)
                if not parent or parent.parent_id is not None:
                    error = "하위 문서의 하위로 이동할 수 없습니다."
            if not error:
                if Document.query.filter_by(title=title).first():
                    error = "동일 제목의 문서가 이미 존재합니다."
            if not error:
                d = Document(title=title, content=content, parent_id=sel_parent_id)
                db.session.add(d); db.session.commit()
                db.session.add(Log(action="create", doc_id=d.id, doc_title=d.title, author=author))
                db.session.commit()
                return redirect(url_for('view_document', doc_id=d.id))
        return render_template("edit.html", mode="new", form=form, error=error, **_ctx())

    @app.route("/edit/<int:doc_id>", methods=["GET","POST"])
    def edit_document(doc_id):
        d = Document.query.get_or_404(doc_id)
        error = None
        if request.method == "POST":
            title = request.form.get("title","").strip()
            content = request.form.get("content","")
            sel_parent_id = request.form.get("parent_id") or None
            author = request.form.get("author","").strip()
            reason = request.form.get("reason","").strip()

            # Enforce single-level nesting: only root can be parent
            if sel_parent_id:
                sel_parent_id = int(sel_parent_id)
                parent = Document.query.get(sel_parent_id)
                if not parent or parent.parent_id is not None:
                    error = "하위 문서의 하위로 이동할 수 없습니다."

            # unique title check
            other = Document.query.filter(Document.id != d.id, Document.title == title).first()
            if not error and other:
                error = "동일 제목의 문서가 이미 존재합니다."

            if not error:
                d.title = title
                d.content = content
                d.parent_id = sel_parent_id
                db.session.commit()
                db.session.add(Log(action="update", doc_id=d.id, doc_title=d.title, author=author, reason=reason))
                db.session.commit()
                return redirect(url_for('view_document', doc_id=d.id))

        form = {"title": d.title, "content": d.content, "parent_id": d.parent_id, "author": ""}
        return render_template("edit.html", mode="edit", form=form, error=error, **_ctx())

    @app.route("/logs")
    def view_logs():
        logs = Log.query.order_by(Log.created_at.desc()).limit(300).all()
        return render_template("logs.html", logs=logs, **_ctx())

    return app

app = create_app()
