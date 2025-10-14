import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from sqlalchemy import text, Table, Column, Integer, String, DateTime, MetaData, inspect
from werkzeug.security import generate_password_hash, check_password_hash

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///db.sqlite3'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    return app

app = create_app()
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ------------- DB bootstrap: ensure user table & password column -------------
with app.app_context():
    insp = inspect(db.engine)
    if not insp.has_table("user"):
        # fresh DB: create robust user table
        md = MetaData()
        Table("user", md,
            Column("id", Integer, primary_key=True),
            Column("email", String(255), unique=True, nullable=False, index=True),
            Column("password_hash", String(255), nullable=False),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        )
        md.create_all(db.engine)
    else:
        cols = {c['name'] for c in insp.get_columns("user")}
        if "password" not in cols and "password_hash" not in cols:
            # add password_hash column if neither exists
            try:
                db.session.execute(text('ALTER TABLE "user" ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT ""'))
                db.session.commit()
            except Exception:
                db.session.rollback()

# ------------- Models (password intentionally not mapped to avoid column mismatches) -------------
class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, default="", nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

@login_manager.user_loader
def load_user(user_id:int):
    return db.session.get(User, int(user_id))

# Helper to decide which password column exists
def _password_column_name()->str:
    cols = {c['name'] for c in inspect(db.engine).get_columns("user")}
    return "password" if "password" in cols else "password_hash"

# ------------- Routes -------------
@app.route('/')
def index():
    docs = Document.query.order_by(Document.created_at.desc()).all()
    return render_template('index.html', docs=docs)

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        pw = request.form.get('password') or ''
        agree = request.form.get('agree') == 'on'

        if not email or not pw:
            flash('이메일과 비밀번호를 모두 입력해주세요.', 'error'); return redirect(url_for('register'))
        if not agree:
            flash('개인정보 처리 및 이용약관에 동의해야 가입할 수 있습니다.', 'error'); return redirect(url_for('register'))

        # already exists?
        exists = db.session.execute(text('SELECT 1 FROM "user" WHERE email=:email LIMIT 1'), {'email': email}).first()
        if exists:
            flash('이미 가입된 이메일입니다. 로그인해주세요.', 'info'); return redirect(url_for('login'))

        pw_hash = generate_password_hash(pw)
        col = _password_column_name()
        db.session.execute(text(f'INSERT INTO "user"(email, {col}, created_at) VALUES (:email, :pw, :ts)'),
                           {'email': email, 'pw': pw_hash, 'ts': datetime.utcnow()})
        db.session.commit()
        # log in
        uid = db.session.execute(text('SELECT id FROM "user" WHERE email=:email'), {'email':email}).scalar()
        if uid:
            user = db.session.get(User, uid)
            login_user(user)
            flash('가입이 완료되었습니다.', 'success')
            return redirect(url_for('index'))
        flash('가입 처리 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        pw = request.form.get('password') or ''
        if not email or not pw:
            flash('이메일과 비밀번호를 입력해주세요.', 'error'); return redirect(url_for('login'))
        # Fetch hashed password via COALESCE to support either column name
        row = db.session.execute(text('SELECT id, email, COALESCE(password, password_hash) AS pw FROM "user" WHERE email=:email LIMIT 1'),
                                 {'email': email}).first()
        if not row or not row.pw or not check_password_hash(row.pw, pw):
            flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error'); return redirect(url_for('login'))
        user = db.session.get(User, row.id)
        login_user(user)
        flash('로그인되었습니다.', 'success'); return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('index'))

@app.route('/healthz')
def healthz():
    return {'status':'ok'}
