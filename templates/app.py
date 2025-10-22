
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, g, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.orm import synonym
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///byeollae.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    # real column in DB
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    # legacy columns that might exist but are optional; keep to avoid mapper errors
    pw = db.Column(db.String(255), nullable=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    # real column name is 'content' in DB
    content = db.Column(db.Text, nullable=False)
    # provide backward-compatible attribute so templates/code can still use obj.body
    body = synonym('content')
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)

@app.before_request
def load_user():
    g.user = None
    uid = session.get('uid')
    if uid:
        g.user = User.query.get(uid)

@app.route('/')
def index():
    # Exclude system docs (terms, privacy) from the list
    docs = (Document.query
            .filter_by(is_system=False)
            .order_by(Document.created_at.desc())
            .all())
    return render_template('index.html', docs=docs)

@app.route('/doc/<int:doc_id>')
def doc_view(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.is_system:
        abort(404)
    return render_template('doc.html', doc=doc)

@app.route('/doc/new', methods=['GET', 'POST'])
def doc_new():
    if not g.user:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        if not title:
            title = '(제목 없음)'
        d = Document(title=title, content=body)
        db.session.add(d)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('edit.html', doc=None)

@app.route('/doc/<int:doc_id>/edit', methods=['GET', 'POST'])
def doc_edit(doc_id):
    if not g.user:
        return redirect(url_for('login'))
    doc = Document.query.get_or_404(doc_id)
    if doc.is_system:
        abort(403)
    if request.method == 'POST':
        doc.title = request.form.get('title', doc.title)
        doc.content = request.form.get('body', doc.content)
        db.session.commit()
        return redirect(url_for('doc_view', doc_id=doc.id))
    return render_template('edit.html', doc=doc)

@app.route('/doc/<int:doc_id>/delete', methods=['POST'])
def doc_delete(doc_id):
    if not g.user:
        return redirect(url_for('login'))
    doc = Document.query.get_or_404(doc_id)
    if doc.is_system:
        abort(403)
    db.session.delete(doc)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['uid'] = user.id
            return redirect(url_for('index'))
        return render_template('login.html', error='이메일 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not email or not password:
            return render_template('signup.html', error='이메일/비밀번호를 입력하세요.')
        if User.query.filter_by(email=email).first():
            return render_template('signup.html', error='이미 존재하는 이메일입니다.')
        user = User(email=email)
        user.set_password(password)  # <-- fill password_hash
        db.session.add(user)
        db.session.commit()
        session['uid'] = user.id
        return redirect(url_for('index'))
    return render_template('signup.html')

# Legal docs: view-only, not listed and not editable
@app.route('/legal/terms')
def legal_terms():
    doc = Document.query.filter_by(is_system=True, title='이용약관').first()
    if not doc:
        return render_template('legal.html', title='이용약관', body='(등록된 약관이 없습니다)')
    return render_template('legal.html', title=doc.title, body=doc.content)

@app.route('/legal/privacy')
def legal_privacy():
    doc = Document.query.filter_by(is_system=True, title='개인정보처리방침').first()
    if not doc:
        return render_template('legal.html', title='개인정보처리방침', body='(등록된 방침이 없습니다)')
    return render_template('legal.html', title=doc.title, body=doc.content)

@app.route('/static/<path:filename>')
def static_proxy(filename):
    # keep compatibility if needed
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(debug=True)
