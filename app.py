import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# --- DB 설정 ---
uri = os.environ.get("DATABASE_URL", "")
if uri.startswith("postgresql://"):
    uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
if "sslmode=" not in uri:
    uri += ("&" if "?" in uri else "?") + "sslmode=require"

app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- 모델 정의 ---
class Page(db.Model):
    __tablename__ = "pages"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    content = db.Column(db.Text)
    parent_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PageLog(db.Model):
    __tablename__ = "page_logs"
    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer)
    author = db.Column(db.String)
    action = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# --- 라우트 ---
@app.route("/")
def index():
    pages = Page.query.all()
    return render_template("index.html", pages=pages)

@app.route("/pages/new", methods=["GET","POST"])
def new_page():
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        p = Page(title=title, content=content)
        db.session.add(p)
        db.session.commit()
        log = PageLog(page_id=p.id, author="system", action="create")
        db.session.add(log)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("new_page.html")

@app.route("/p/<int:pid>")
def view_page(pid):
    page = Page.query.get_or_404(pid)
    logs = PageLog.query.filter_by(page_id=pid).all()
    return render_template("view_page.html", page=page, logs=logs)
