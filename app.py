import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = "supersecret"

# DATABASE_URL 보정
db_url = os.getenv("DATABASE_URL")
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    if "sslmode" not in db_url:
        db_url += "&sslmode=require&connect_timeout=10" if "?" in db_url else "?sslmode=require&connect_timeout=10"
    parsed = urlparse(db_url)
    if parsed.port == 5432 and parsed.hostname and parsed.hostname.endswith("supabase.co"):
        db_url = db_url.replace(":5432", ":6543", 1)
else:
    db_url = "sqlite:///local.db"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)


class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer)
    action = db.Column(db.String(50))
    summary = db.Column(db.String(200))


with app.app_context():
    try:
        db.create_all()
        print("[DB] Connected OK")
    except OperationalError as e:
        print(f"[DB] Connection failed: {e}")


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
        log = Log(page_id=page.id, action="create", summary=f"{title} 생성")
        db.session.add(log)
        db.session.commit()
        flash("문서가 생성되었습니다.")
        return redirect(url_for("index"))
    return render_template("new.html")


@app.route("/view/<int:page_id>")
def view_page(page_id):
    page = Page.query.get_or_404(page_id)
    logs = Log.query.filter_by(page_id=page.id).all()
    return render_template("view.html", page=page, logs=logs)


@app.route("/edit/<int:page_id>", methods=["GET", "POST"])
def edit_page(page_id):
    page = Page.query.get_or_404(page_id)
    if request.method == "POST":
        page.title = request.form["title"]
        page.content = request.form["content"]
        db.session.commit()
        log = Log(page_id=page.id, action="edit", summary=f"{page.title} 수정")
        db.session.add(log)
        db.session.commit()
        flash("문서가 수정되었습니다.")
        return redirect(url_for("view_page", page_id=page.id))
    return render_template("edit.html", page=page)


if __name__ == "__main__":
    app.run(debug=True)
