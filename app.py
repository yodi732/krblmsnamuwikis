import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# DATABASE_URL 환경변수 불러오기
db_url = os.getenv("DATABASE_URL", "sqlite:///local.db")

# psycopg 접두어 및 옵션 보정
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
if db_url.startswith("postgresql://") and "psycopg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
if "sslmode" not in db_url:
    db_url += "?sslmode=require&connect_timeout=10"
elif "connect_timeout" not in db_url:
    db_url += "&connect_timeout=10"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Page(db.Model):
    __tablename__ = "pages"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PageLog(db.Model):
    __tablename__ = "page_logs"
    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer)
    action = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

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
        log = PageLog(page_id=page.id, action="created")
        db.session.add(log)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("new.html")

@app.route("/p/<int:page_id>")
def view_page(page_id):
    page = Page.query.get_or_404(page_id)
    logs = PageLog.query.filter_by(page_id=page.id).all()
    return render_template("view.html", page=page, logs=logs)

@app.route("/p/<int:page_id>/edit", methods=["GET", "POST"])
def edit_page(page_id):
    page = Page.query.get_or_404(page_id)
    if request.method == "POST":
        page.title = request.form["title"]
        page.content = request.form["content"]
        db.session.commit()
        log = PageLog(page_id=page.id, action="edited")
        db.session.add(log)
        db.session.commit()
        return redirect(url_for("view_page", page_id=page.id))
    return render_template("edit.html", page=page)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
