import os
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "fallback_key_change_me")
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URI")
    if not database_url:
        database_url = "sqlite:///local.db"

    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "10")),
        "connect_args": {"connect_timeout": int(os.environ.get("DB_CONNECT_TIMEOUT", "10"))},
    }

    db.init_app(app)

    app.config["_DB_READY"] = False
    app.config["_DB_LAST_CHECK"] = 0.0
    app.config["_DB_CHECK_INTERVAL"] = 30.0

    class Page(db.Model):
        __tablename__ = "pages"
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(200), nullable=False, unique=True)
        content = db.Column(db.Text, nullable=False, default="")
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    app.Page = Page

    def check_db(force=False):
        now = time.time()
        if not force and (now - app.config["_DB_LAST_CHECK"]) < app.config["_DB_CHECK_INTERVAL"]:
            return app.config["_DB_READY"]
        try:
            with app.app_context():
                with db.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
            app.config["_DB_READY"] = True
        except Exception as e:
            app.logger.error("DB ping failed: %s", repr(e))
            app.config["_DB_READY"] = False
        app.config["_DB_LAST_CHECK"] = now
        return app.config["_DB_READY"]

    def init_db():
        try:
            with app.app_context():
                db.create_all()
            app.config["_DB_READY"] = True
        except Exception as e:
            app.logger.error("DB init skipped (not ready): %s", repr(e))
            app.config["_DB_READY"] = False

    init_db()

    @app.context_processor
    def inject_flags():
        return {"DB_READY": check_db()}

    @app.get("/healthz")
    def healthz():
        ok = check_db(force=True)
        status = {"app": "ok", "db": "ok" if ok else "down"}
        return (status, 200 if ok else 503)

    @app.route("/", methods=["GET"])
    def index():
        if not check_db():
            flash("데이터베이스에 연결할 수 없습니다. 환경변수 DATABASE_URL을 확인하세요.", "error")
            pages = []
        else:
            try:
                pages = Page.query.order_by(Page.updated_at.desc()).all()
            except SQLAlchemyError as e:
                app.logger.error("Query failed: %s", repr(e))
                pages = []
                flash("데이터를 불러오지 못했습니다.", "error")
        return render_template("index.html", pages=pages)

    @app.route("/pages/new", methods=["GET", "POST"])
    def new_page():
        if request.method == "POST":
            title = (request.form.get("title") or "").strip()
            content = request.form.get("content") or ""
            if not check_db():
                flash("DB 연결이 안되어 저장할 수 없습니다.", "error")
                return redirect(url_for("index"))
            if not title:
                flash("제목을 입력하세요.", "error")
                return redirect(url_for("new_page"))
            try:
                page = Page(title=title, content=content)
                db.session.add(page)
                db.session.commit()
                flash("문서가 생성되었습니다.", "success")
                return redirect(url_for("index"))
            except SQLAlchemyError as e:
                db.session.rollback()
                flash("저장 중 오류가 발생했습니다. (중복 제목일 수 있음)", "error")
                app.logger.error("Insert failed: %s", repr(e))
                return redirect(url_for("new_page"))
        return render_template("new.html")

    @app.route("/pages/<int:pid>/edit", methods=["GET", "POST"])
    def edit_page(pid):
        if not check_db():
            flash("DB 연결이 안되어 편집할 수 없습니다.", "error")
            return redirect(url_for("index"))
        page = Page.query.get_or_404(pid)
        if request.method == "POST":
            page.title = (request.form.get("title") or page.title).strip()
            page.content = request.form.get("content") or page.content
            try:
                db.session.commit()
                flash("저장되었습니다.", "success")
                return redirect(url_for("index"))
            except SQLAlchemyError as e:
                db.session.rollback()
                flash("저장 중 오류가 발생했습니다.", "error")
                app.logger.error("Update failed: %s", repr(e))
        return render_template("edit.html", page=page)

    @app.route("/pages/<int:pid>/delete", methods=["POST"])
    def delete_page(pid):
        if not check_db():
            flash("DB 연결이 안되어 삭제할 수 없습니다.", "error")
            return redirect(url_for("index"))
        page = Page.query.get_or_404(pid)
        try:
            db.session.delete(page)
            db.session.commit()
            flash("삭제되었습니다.", "success")
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("삭제 중 오류가 발생했습니다.", "error")
            app.logger.error("Delete failed: %s", repr(e))
        return redirect(url_for("index"))

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
