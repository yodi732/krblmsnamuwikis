# app.py
# Flask app for Byeollae Wiki (final version)
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///wiki.db').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv('SECRET_KEY', 'dev_secret')

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    pw_hash = db.Column(db.String(255), nullable=False)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, unique=True)
    body = db.Column(db.Text, default='')
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    parent = db.relationship('Document', remote_side=[id], backref='children')

@app.before_first_request
def init_db():
    with app.app_context():
        inspector = db.inspect(db.engine)
        cols = [c['name'] for c in inspector.get_columns('document')]
        if 'body' not in cols:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE document ADD COLUMN body TEXT DEFAULT "";'))
            print('✅ body column created')
        db.create_all()

        # Auto-generate legal docs
        for title, content in [('이용약관', '본 서비스는 교육 목적의 위키입니다.\n사용자는 타인의 권리를 침해하지 않으며, 법령 및 학교 규정을 준수해야 합니다.\n관리자가 필요하다고 판단할 경우 문서를 수정·삭제할 수 있습니다.'),
                               ('개인정보처리방침', '본 위키는 서비스 제공을 위해 최소한의 개인정보만 수집·이용합니다.\n수집 항목: 학교 이메일(@bl-m.kr), 비밀번호(해시처리), 로그인·문서 활동 로그\n이용 목적: 사용자 인증, 서비스 운영 기록 관리\n보관 및 파기: 회원 탈퇴 시 즉시 삭제, 단 법령상 보관이 필요한 로그는 안전하게 보관 후 파기')]:
            if not Document.query.filter_by(title=title).first():
                db.session.add(Document(title=title, body=content))
        db.session.commit()
        print('✅ Database check complete: schema verified/created')

@app.route('/')
def home():
    docs = Document.query.filter_by(parent_id=None).order_by(Document.title.asc()).all()
    return render_template('home.html', docs=docs, me=session.get('user'))

@app.route('/doc/<title>')
def doc_view(title):
    doc = Document.query.filter_by(title=title).first()
    if not doc:
        return redirect(url_for('home'))
    return render_template('doc.html', doc=doc)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        pw = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.pw_hash, pw):
            session['user'] = user.email
            return redirect(url_for('home'))
        flash('이메일 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        pw = generate_password_hash(request.form['password'])
        if not email.endswith('@bl-m.kr'):
            flash('학교 이메일(@bl-m.kr)만 허용됩니다.')
            return redirect(url_for('register'))
        db.session.add(User(email=email, pw_hash=pw))
        db.session.commit()
        flash('회원가입 완료. 로그인해주세요.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/create', methods=['GET', 'POST'])
def create():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        parent_id = request.form.get('parent_id') or None
        if parent_id:
            parent = Document.query.get(parent_id)
            if parent and parent.parent_id is not None:
                flash('하위문서의 하위문서는 만들 수 없습니다.')
                return redirect(url_for('home'))
        db.session.add(Document(title=title, parent_id=parent_id, body=''))
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('create.html', docs=Document.query.all())

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
