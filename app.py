import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def make_database_uri():
    raw = (os.environ.get("DATABASE_URL") or "").strip()
    if not raw:
        return "sqlite:///local.db"
    if raw.startswith("postgres://"):
        raw = "postgresql+psycopg://" + raw.split("://", 1)[1]
    if raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+psycopg://", 1)
    if "sslmode=" not in raw and raw.startswith("postgresql+psycopg://"):
        sep = "&" if "?" in raw else "?"
        raw = f"{raw}{sep}sslmode=require&connect_timeout=10"
    return raw

def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = make_database_uri()
    app.config["SQLALCHEMY_TRACKMODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 5,
        "connect_args": {"options": "-c statement_timeout=15000"},
    }

    db.init_app(app)

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

    def ctx_sidebar():
        tocs = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
        children_map = {t.id: Document.query.filter_by(parent_id=t.id).order_by(Document.title.asc()).all() for t in tocs}
        return dict(tocs=tocs, children_map=children_map)

    @app.get("/healthz")
    def healthz():
        return jsonify(ok=True)

    @app.post("/init-db")
    def init_db():
        try:
            with app.app_context():
                db.create_all()
            return jsonify(status="created")
        except Exception as e:
            return jsonify(error=str(e)), 500

    @app.route("/")
    def home():
        docs = db.session.execute(db.select(Document).order_by(Document.updated_at.desc())).scalars().all()
        return render_template("index.html", docs=docs, **ctx_sidebar())

    @app.route("/doc/<int:doc_id>")
    def view_document(doc_id):
        d = db.session.get(Document, doc_id)
        if not d: abort(404)
        children = db.session.execute(db.select(Document).filter_by(parent_id=doc_id)).scalars().all()
        return render_template("document.html", doc=d, children=children, warning=None, **ctx_sidebar())

    @app.route("/new", methods=["GET","POST"])
    def new_document():
        parent_id = request.args.get("parent_id", type=int)
        form = {"title":"", "content":"", "author":"", "parent_id": parent_id}
        error = None
        if request.method == "POST":
            title = (request.form.get("title") or "").strip()
            content = request.form.get("content") or ""
            author = (request.form.get("author") or "").strip()
            sel_parent_id = request.form.get("parent_id") or None

            if sel_parent_id:
                sel_parent_id = int(sel_parent_id)
                parent = db.session.get(Document, sel_parent_id)
                if (not parent) or (parent.parent_id is not None):
                    error = "하위 문서의 하위로는 만들 수 없습니다."

            if not error and db.session.execute(db.select(Document).filter_by(title=title)).scalar():
                error = "동일 제목의 문서가 이미 존재합니다."

            if not error:
                d = Document(title=title, content=content, parent_id=sel_parent_id)
                db.session.add(d); db.session.commit()
                db.session.add(Log(action="create", doc_id=d.id, doc_title=d.title, author=author))
                db.session.commit()
                return redirect(url_for('view_document', doc_id=d.id))

        tocs = db.session.execute(db.select(Document).filter_by(parent_id=None).order_by(Document.title.asc())).scalars().all()
        return render_template("edit.html", mode="new", form=form, error=error, tocs=tocs, **ctx_sidebar())

    @app.route("/edit/<int:doc_id>", methods=["GET","POST"])
    def edit_document(doc_id):
        d = db.session.get(Document, doc_id)
        if not d: abort(404)
        error = None
        if request.method == "POST":
            title = (request.form.get("title") or "").strip()
            content = request.form.get("content") or ""
            sel_parent_id = request.form.get("parent_id") or None
            author = (request.form.get("author") or "").strip()
            reason = (request.form.get("reason") or "").strip()

            if sel_parent_id:
                sel_parent_id = int(sel_parent_id)
                parent = db.session.get(Document, sel_parent_id)
                if (not parent) or (parent.parent_id is not None):
                    error = "하위 문서의 하위로 이동할 수 없습니다."

            other = db.session.execute(db.select(Document).filter(Document.id != d.id, Document.title == title)).scalar()
            if not error and other:
                error = "동일 제목의 문서가 이미 존재합니다."

            if not error:
                d.title, d.content, d.parent_id = title, content, sel_parent_id
                db.session.commit()
                db.session.add(Log(action="update", doc_id=d.id, doc_title=d.title, author=author, reason=reason))
                db.session.commit()
                return redirect(url_for('view_document', doc_id=d.id))

        tocs = db.session.execute(db.select(Document).filter_by(parent_id=None).order_by(Document.title.asc())).scalars().all()
        form = {"title": d.title, "content": d.content, "parent_id": d.parent_id, "author": ""}
        return render_template("edit.html", mode="edit", form=form, error=error, tocs=tocs, **ctx_sidebar())

    @app.route("/logs")
    def view_logs():
        logs = db.session.execute(db.select(Log).order_by(Log.created_at.desc()).limit(300)).scalars().all()
        return render_template("logs.html", logs=logs, **ctx_sidebar())

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
