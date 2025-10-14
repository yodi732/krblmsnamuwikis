\
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

    # DB URL selection: prefer SQLite unless a valid postgres URL is supplied
    default_sqlite = 'sqlite:///app.db'
    db_url = os.getenv('DATABASE_URL', default_sqlite)
    # Render sometimes sets DATABASE_URL to empty or invalid; guard it
    if not db_url or db_url.strip() == '':
        db_url = default_sqlite

    # If postgres URL but psycopg is not installed, fall back to sqlite to avoid crash
    if db_url.startswith('postgres://') or db_url.startswith('postgresql://'):
        try:
            import psycopg  # noqa: F401
        except Exception:
            # fallback
            db_url = default_sqlite

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    return app

app = create_app()
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

########
# Models
########
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # demo only
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_id(self):
        return str(self.id)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False, default='')
    author_email = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship('Document', remote_side=[id], backref='children')

########
# Auth
########
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

########
# Helpers
########
def top_level_docs():
    return Document.query.filter_by(parent_id=None).order_by(Document.updated_at.desc()).all()

def is_sub_sub(parent_id):
    if parent_id is None:
        return False
    parent = Document.query.get(parent_id)
    if parent and parent.parent_id is not None:
        return True
    return False

#############
# DB bootstrap
#############
with app.app_context():
    db.create_all()
    # seed demo user once
    if not User.query.filter_by(email='admin@school.kr').first():
        db.session.add(User(email='admin@school.kr', password='admin'))
        db.session.commit()

########
# Routes
########
@app.route('/')
def index():
    parents = top_level_docs()
    return render_template('index.html', parents=parents)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        agree = request.form.get('agree')
        if not email or not password:
            flash('이메일과 비밀번호를 입력해 주세요.', 'error')
        elif not agree:
            flash('약관에 동의해야 가입이 가능합니다.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('이미 가입된 이메일입니다.', 'error')
        else:
            db.session.add(User(email=email, password=password))
            db.session.commit()
            flash('가입이 완료되었습니다. 로그인해 주세요.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('index'))
        flash('로그인 실패: 이메일 또는 비밀번호를 확인해 주세요.', 'error')
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('로그아웃되었습니다.', 'success')
    return redirect(url_for('login'))

@app.route('/withdraw', methods=['POST'])
@login_required
def withdraw():
    # delete user and their documents
    email = current_user.email
    Document.query.filter_by(author_email=email).delete()
    u = User.query.get(current_user.id)
    logout_user()
    db.session.delete(u)
    db.session.commit()
    flash('회원탈퇴가 완료되었습니다.', 'success')
    return redirect(url_for('register'))

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        parent_id = request.form.get('parent_id')
        parent_id = int(parent_id) if parent_id else None

        if is_sub_sub(parent_id):
            flash('하위문서의 하위문서는 만들 수 없습니다.', 'error')
            return redirect(url_for('create'))

        if not title:
            flash('제목을 입력해 주세요.', 'error')
            return redirect(url_for('create'))

        doc = Document(title=title, body=body, parent_id=parent_id, author_email=current_user.email)
        db.session.add(doc)
        db.session.commit()
        return redirect(url_for('view_document', doc_id=doc.id))

    parents = top_level_docs()
    return render_template('create.html', parents=parents)

@app.route('/doc/<int:doc_id>')
def view_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return render_template('view.html', doc=doc)

@app.route('/doc/<int:doc_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        if not title:
            flash('제목을 입력해 주세요.', 'error')
            return redirect(url_for('edit_document', doc_id=doc.id))
        doc.title = title
        doc.body = body
        db.session.commit()
        return redirect(url_for('view_document', doc_id=doc.id))
    return render_template('edit.html', doc=doc)

@app.route('/doc/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    db.session.delete(doc)
    db.session.commit()
    flash('문서를 삭제했습니다.', 'success')
    return redirect(url_for('index'))

########
# Error pages
########
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', msg='페이지를 찾을 수 없습니다.'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', msg='서버 오류가 발생했습니다.'), 500

if __name__ == '__main__':
    app.run(debug=True)
