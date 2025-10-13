import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from urllib.parse import urljoin

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')

db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

MAIL_SERVER = os.environ.get('MAIL_SERVER')
MAIL_PORT   = int(os.environ.get('MAIL_PORT', '587'))
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
MAIL_SENDER  = os.environ.get('MAIL_SENDER', '별내위키 <no-reply@example.com>')
APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')

ts = URLSafeTimedSerializer(app.config['SECRET_KEY'])

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    agreed_at = db.Column(db.DateTime, nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    documents = db.relationship('Document', backref='author', lazy='dynamic')

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    parent_id = db.Column(db.Integer, nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class Log(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user_email  = db.Column(db.String(255), nullable=True, index=True)
    action      = db.Column(db.String(64), nullable=False)
    object_type = db.Column(db.String(64), nullable=True)
    object_id   = db.Column(db.Integer, nullable=True)
    detail      = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', lazy='joined')

with app.app_context():
    db.create_all()

def write_log(action, object_type=None, object_id=None, detail=None):
    uid = current_user.id if current_user.is_authenticated else None
    email = current_user.email if current_user.is_authenticated else None
    db.session.add(Log(
        user_id=uid,
        user_email=email,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=detail
    ))
    db.session.commit()

def send_email(to_email, subject, html):
    msg = MIMEText(html, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = MAIL_SENDER
    msg['To'] = to_email

    if MAIL_USE_SSL:
        import ssl
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, context=context) as server:
            if MAIL_USERNAME and MAIL_PASSWORD:
                server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_SENDER, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            if MAIL_USE_TLS:
                server.starttls()
            if MAIL_USERNAME and MAIL_PASSWORD:
                server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_SENDER, [to_email], msg.as_string())

def verification_link(email):
    token = ts.dumps({'email': email, 'purpose': 'verify'})
    return url_for('verify_email', token=token, _external=True)

def reset_link(email):
    token = ts.dumps({'email': email, 'purpose': 'reset'})
    return url_for('reset_password', token=token, _external=True)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

from flask import render_template_string

@app.route('/')
def index():
    docs = Document.query.filter_by(parent_id=None).order_by(Document.created_at.desc()).all()
    return render_template('index.html', documents=docs)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','').strip()
        agree = request.form.get('agree') == 'on'

        if not email or not password:
            flash('이메일과 비밀번호를 입력하세요.')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('이미 존재하는 이메일입니다.')
            return redirect(url_for('register'))

        user = User(email=email, agreed_at=datetime.utcnow() if agree else None)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        link = verification_link(email)
        send_email(email, '[별내위키] 이메일 인증', f'<p>아래 링크를 클릭해 이메일을 인증하세요:</p><p><a href="{link}">{link}</a></p>')

        write_log('REGISTER', detail=f'email={email}')
        flash('회원가입 완료! 이메일로 인증 링크를 보냈습니다.')
        return redirect(url_for('verify_pending'))

    return render_template('register.html')

@app.route('/verify-pending')
def verify_pending():
    return render_template('verify_pending.html')

@app.route('/verify/<token>')
def verify_email(token):
    try:
        data = ts.loads(token, max_age=60*60*24)
        if data.get('purpose') != 'verify':
            raise BadSignature('invalid purpose')
    except (BadSignature, SignatureExpired):
        flash('토큰이 유효하지 않거나 만료되었습니다.')
        return redirect(url_for('login'))

    email = data.get('email')
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('사용자를 찾을 수 없습니다.')
        return redirect(url_for('login'))

    user.email_verified = True
    db.session.commit()
    write_log('VERIFY_EMAIL', detail=f'email={email}')
    flash('이메일 인증이 완료되었습니다. 로그인하세요.')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','').strip()

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('이메일 또는 비밀번호가 올바르지 않습니다.')
            return redirect(url_for('login'))

        if not user.email_verified:
            flash('이메일 인증 후 로그인할 수 있습니다.')
            return redirect(url_for('verify_pending'))

        login_user(user)
        write_log('LOGIN', detail=f'email={email}')
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    write_log('LOGOUT', detail=f'email={current_user.email}')
    logout_user()
    flash('로그아웃 되었습니다.')
    return redirect(url_for('index'))

@app.route('/forgot', methods=['GET','POST'])
def forgot():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            link = reset_link(email)
            send_email(email, '[별내위키] 비밀번호 재설정', f'<p>아래 링크에서 비밀번호를 재설정하세요(24시간 유효):</p><p><a href="{link}">{link}</a></p>')
            write_log('REQUEST_RESET', detail=f'email={email}')
        flash('가능하다면 비밀번호 재설정 메일을 보냈습니다.')
        return redirect(url_for('login'))
    return render_template('forgot.html')

@app.route('/reset/<token>', methods=['GET','POST'])
def reset_password(token):
    try:
        data = ts.loads(token, max_age=60*60*24)
        if data.get('purpose') != 'reset':
            raise BadSignature('invalid purpose')
    except (BadSignature, SignatureExpired):
        flash('토큰이 유효하지 않거나 만료되었습니다.')
        return redirect(url_for('login'))

    email = data.get('email')
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('사용자를 찾을 수 없습니다.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        newpw = request.form.get('password','').strip()
        if not newpw:
            flash('새 비밀번호를 입력하세요.')
            return redirect(request.url)
        user.set_password(newpw)
        db.session.commit()
        write_log('RESET_PASSWORD', detail=f'email={email}')
        flash('비밀번호가 변경되었습니다. 로그인하세요.')
        return redirect(url_for('login'))
    return render_template('reset.html', email=email)

@app.post('/account/delete')
@login_required
def delete_account():
    email = current_user.email
    Document.query.filter_by(author_id=current_user.id).update({Document.author_id: None})
    db.session.delete(current_user)
    db.session.commit()
    write_log('DELETE_ACCOUNT', detail=f'email={email}')
    flash('회원탈퇴가 완료되었습니다.')
    return redirect(url_for('index'))

@app.route('/logs')
@login_required
def logs():
    items = Log.query.order_by(Log.created_at.desc()).limit(500).all()
    return render_template('logs.html', logs=items)

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/document/new', methods=['GET','POST'])
@login_required
def new_doc():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        content = request.form.get('content','').strip()
        if not title or not content:
            flash('제목과 본문을 입력하세요.')
            return redirect(url_for('new_doc'))
        d = Document(title=title, content=content, author_id=current_user.id)
        db.session.add(d)
        db.session.commit()
        write_log('CREATE_DOC', 'Document', d.id, detail=f'title={title}')
        return redirect(url_for('index'))
    return render_template('new_doc.html')

if __name__ == '__main__':
    app.run(debug=True)
