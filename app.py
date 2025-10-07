from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "secret"

# DB 연결 (Supabase DATABASE_URL 환경변수 사용)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# 모델 정의
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

# 첫 실행 시 테이블 자동 생성
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    pages = Page.query.all()
    return render_template("index.html", pages=pages)

@app.route('/new', methods=['GET','POST'])
def new_page():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        page = Page(title=title, content=content)
        db.session.add(page)
        db.session.commit()
        flash("문서가 생성되었습니다.")
        return redirect(url_for('index'))
    return render_template("new_page.html")

@app.route('/page/<int:pid>')
def view_page(pid):
    page = Page.query.get_or_404(pid)
    return render_template("view_page.html", page=page)

@app.route('/page/<int:pid>/edit', methods=['GET','POST'])
def edit_page(pid):
    page = Page.query.get_or_404(pid)
    if request.method == 'POST':
        page.title = request.form['title']
        page.content = request.form['content']
        db.session.commit()
        flash("문서가 수정되었습니다.")
        return redirect(url_for('view_page', pid=pid))
    return render_template("edit_page.html", page=page)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
