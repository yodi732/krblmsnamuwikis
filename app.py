import os, socket, urllib.parse, logging
from flask import Flask, request, redirect, url_for, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

db = SQLAlchemy()
log = logging.getLogger(__name__)

def _mask_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
        netloc = parsed.netloc
        if "@" in netloc and ":" in netloc.split("@")[0]:
            user, host = netloc.split("@", 1)[0].split(":", 1)
            netloc_masked = netloc.replace(f"{user}:{host.split('@')[0]}", f"{user}:****")
        else:
            netloc_masked = netloc
        return urllib.parse.urlunsplit((parsed.scheme, netloc_masked, parsed.path, parsed.query, parsed.fragment))
    except Exception:
        return "<cannot-mask>"

def _dns_diagnose(hostname: str):
    try:
        infos = socket.getaddrinfo(hostname, None)
        addrs = sorted({i[4][0] for i in infos})
        log.info(f"[DIAG] DNS {hostname} -> {addrs}")
    except Exception as e:
        log.error(f"[DIAG] DNS FAILED for {hostname}: {e}")

def create_app():
    app = Flask(__name__)

    db_url = os.getenv("DATABASE_URL", "sqlite:///local.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg://")
    if "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url += sep + "sslmode=require&connect_timeout=10"

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

    log.info(f"[DIAG] DATABASE_URL = { _mask_url(db_url) }")
    try:
        host_port = urllib.parse.urlsplit(db_url).netloc.split("@")[-1]
        host = host_port.split(":")[0]
        if host:
            _dns_diagnose(host)
    except Exception as e:
        log.error(f"[DIAG] Could not parse host from DATABASE_URL: {e}")

    db.init_app(app)

    with app.app_context():
        try:
            db.session.execute(text("select 1"))
            log.info("[DIAG] DB ping OK")
        except OperationalError as e:
            log.error(f"[DIAG] DB ping FAILED: {e}")
        try:
            db.create_all()
            log.info("[DIAG] db.create_all() OK")
        except Exception as e:
            log.error(f"[DIAG] db.create_all() FAILED: {e}")

    class Page(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(200), nullable=False)
        content = db.Column(db.Text, nullable=False)

    @app.route("/")
    def index():
        pages = Page.query.all()
        return render_template("index.html", pages=pages)

    @app.route("/new", methods=["GET", "POST"])
    def new_page():
        if request.method == "POST":
            title = request.form["title"]
            content = request.form["content"]
            page = Page(title=title, content=content)
            db.session.add(page)
            db.session.commit()
            return redirect(url_for("index"))
        return render_template("new.html")

    @app.route("/view/<int:page_id>")
    def view_page(page_id):
        page = Page.query.get_or_404(page_id)
        return render_template("view.html", page=page)

    @app.route("/edit/<int:page_id>", methods=["GET", "POST"])
    def edit_page(page_id):
        page = Page.query.get_or_404(page_id)
        if request.method == "POST":
            page.title = request.form["title"]
            page.content = request.form["content"]
            db.session.commit()
            return redirect(url_for("view_page", page_id=page.id))
        return render_template("edit.html", page=page)

    @app.get("/healthz")
    def healthz():
        return "ok", 200

    @app.get("/dbcheck")
    def dbcheck():
        try:
            db.session.execute(text("select 1"))
            return jsonify({"db": "ok"}), 200
        except Exception as e:
            return jsonify({"db": "error", "detail": str(e)}), 500

    return app

app = create_app()
