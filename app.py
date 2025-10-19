import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    pw_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_system = db.Column(db.Boolean, default=False, nullable=False)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def current_user():
    uid = session.get('uid')
    if not uid: return None
    return User.query.get(uid)

def log(event):
    db.session.add(Log(event=event))
    db.session.commit()

with app.app_context():
    db.create_all()
    if not Document.query.filter_by(is_system=True, title='이용약관').first():
        db.session.add(Document(title='이용약관', content='본 이용약관은 별내위키 서비스 이용에 필요한 기본 사항을 규정합니다.', is_system=True))
    if not Document.query.filter_by(is_system=True, title='개인정보처리방침').first():
        db.session.add(Document(title='개인정보처리방침', content='별내위키는 서비스 제공에 필요한 최소한의 개인정보만을 수집·이용하며 관련 법령을 준수합니다.', is_system=True))
    db.session.commit()

@app.route('/')
def home():
    roots = Document.query.filter_by(parent_id=None).order_by(Document.is_system.desc(), Document.id.asc()).all()
    recents = Document.query.order_by(Document.updated_at.desc()).limit(10).all()
    return render_template('home.html', roots=roots, recents=recents, me=current_user())

@app.route('/doc/<int:doc_id>')
def view_doc(doc_id):
    doc = Document.query.get_or_404(doc_id)
    parent = Document.query.get(doc.parent_id) if doc.parent_id else None
    children = Document.query.filter_by(parent_id=doc.id).order_by(Document.title.asc()).all()
    return render_template('view.html', doc=doc, parent=parent, children=children, me=current_user())

@app.route('/create', methods=['GET','POST'])
def create_doc():
    user = current_user()
    if not user: abort(403)
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        content = request.form.get('content','').strip()
        parent_id = request.form.get('parent_id') or None
        if not title or not content: abort(400)
        doc = Document(title=title, content=content, parent_id=int(parent_id) if parent_id else None, updated_at=datetime.utcnow())
        db.session.add(doc)
        db.session.commit()
        log(f'{user.email} 문서 생성: {title}')
        return redirect(url_for('view_doc', doc_id=doc.id))
    all_docs = Document.query.order_by(Document.title.asc()).all()
    return render_template('create.html', all_docs=all_docs, me=user)

@app.route('/edit/<int:doc_id>', methods=['GET','POST'])
def edit_doc(doc_id):
    user = current_user()
    if not user: abort(403)
    doc = Document.query.get_or_404(doc_id)
    if request.method == 'POST':
        doc.content = request.form.get('content','')
        if not doc.is_system:
            doc.title = request.form.get('title','').strip()
            parent_id = request.form.get('parent_id') or None
            doc.parent_id = int(parent_id) if parent_id else None
        doc.updated_at = datetime.utcnow()
        db.session.commit()
        log(f'{user.email} 문서 수정: {doc.title}')
        return redirect(url_for('view_doc', doc_id=doc.id))
    all_docs = Document.query.order_by(Document.title.asc()).all()
    return render_template('edit.html', doc=doc, all_docs=all_docs, me=user)

@app.route('/delete/<int:doc_id>')
def delete_doc(doc_id):
    user = current_user()
    if not user: abort(403)
    doc = Document.query.get_or_404(doc_id)
    if doc.is_system: abort(403)
    child = Document.query.filter_by(parent_id=doc.id).first()
    if child: abort(400)
    title = doc.title
    db.session.delete(doc)
    db.session.commit()
    log(f'{user.email} 문서 삭제: {title}')
    return redirect(url_for('home'))

ALLOW_DOMAIN = '@bl-m.kr'

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        pw = request.form.get('password','')
        agree_terms = request.form.get('agree_terms')
        agree_privacy = request.form.get('agree_privacy')
        if not email.endswith(ALLOW_DOMAIN):
            return render_template('signup.html', error='학교 이메일(@bl-m.kr)만 가입 가능합니다.', me=current_user())
        if not (agree_terms and agree_privacy):
            return render_template('signup.html', error='약관 및 개인정보처리방침에 동의해야 합니다.', me=current_user())
        if User.query.filter_by(email=email).first():
            return render_template('signup.html', error='이미 가입된 이메일입니다.', me=current_user())
        user = User(email=email, pw_hash=generate_password_hash(pw))
        db.session.add(user)
        db.session.commit()
        session['uid'] = user.id
        log(f'{email} 가입')
        return redirect(url_for('home'))
    return render_template('signup.html', error=None, me=current_user())

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        pw = request.form.get('password','')
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.pw_hash, pw) or not email.endswith(ALLOW_DOMAIN):
            return render_template('login.html', error='이메일 또는 비밀번호가 올바르지 않습니다.', me=current_user())
        session['uid'] = user.id
        log(f'{email} 로그인')
        return redirect(url_for('home'))
    return render_template('login.html', error=None, me=current_user())

@app.route('/logout')
def logout():
    u = current_user()
    if u: log(f'{u.email} 로그아웃')
    session.clear()
    return redirect(url_for('home'))

@app.route('/withdraw')
def withdraw():
    if not current_user(): abort(403)
    return render_template('withdraw.html', me=current_user())

@app.route('/withdraw/confirm')
def withdraw_confirm():
    u = current_user()
    if not u: abort(403)
    email = u.email
    session.clear()
    db.session.delete(u)
    db.session.commit()
    log(f'{email} 회원탈퇴')
    return redirect(url_for('home'))

@app.route('/logs')
def view_logs():
    if not current_user(): abort(403)
    logs = Log.query.order_by(Log.created_at.desc()).limit(200).all()
    return render_template('logs.html', logs=logs, me=current_user())

@app.route('/terms')
def open_terms():
    d = Document.query.filter_by(is_system=True, title='이용약관').first()
    if not d: abort(404)
    return redirect(url_for('view_doc', doc_id=d.id))

@app.route('/privacy')
def open_privacy():
    d = Document.query.filter_by(is_system=True, title='개인정보처리방침').first()
    if not d: abort(404)
    return redirect(url_for('view_doc', doc_id=d.id))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
