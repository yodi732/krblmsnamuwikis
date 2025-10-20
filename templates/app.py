import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select, text
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret')
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    pw_hash = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    content = db.Column(db.Text, default='')
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

with app.app_context():
    db.create_all()
    # Seed terms/privacy if missing (only once)
    def seed(title, content):
        doc = db.session.execute(select(Document).where(Document.title == title)).scalar_one_or_none()
        if not doc:
            db.session.add(Document(title=title, content=content, is_system=True))
            db.session.commit()
    seed('이용약관', """본 서비스는 교육 목적의 위키입니다. 사용자는 다음을 준수합니다.
1) 타인의 권리를 침해하지 않습니다.
2) 법령과 학교 규정을 준수합니다.
3) 관리자가 판단할 경우 문서를 수정/삭제할 수 있습니다.
""".strip())
    seed('개인정보처리방침', """수집 항목: 학교 이메일(@bl-m.kr), 비밀번호(해시 처리), 로그인/문서 활동 로그
이용 목적: 사용자 인증, 서비스 운영 기록 관리
보관 및 파기: 회원 탈퇴 즉시 정보를 삭제하며, 법령상 보관이 필요한 로그는 해당 기간 보관 후 파기합니다.
제3자 제공/국외이전: 하지 않습니다.
정보주체 권리: 열람·정정·삭제·처리정지 요구 및 동의 철회 가능
보호 조치: 비밀번호는 평문이 아닌 해시로 저장하며, 최소 권한 원칙으로 접근을 통제합니다.
""".strip())

@app.before_request
def load_user():
    uid = session.get('uid')
    g.user = db.session.get(User, uid) if uid else None

@app.route('/')
def index():
    recent = db.session.execute(select(Document).order_by(Document.updated_at.desc()).limit(5)).scalars().all()
    return render_template('index.html', recent=recent)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        pw = request.form.get('password','')
        user = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        # Robust check: if pw_hash missing (legacy row), treat as invalid without crashing
        if (not user) or (not user.pw_hash) or (not check_password_hash(user.pw_hash, pw)):
            flash('이메일 또는 비밀번호가 올바르지 않습니다. (기존 계정의 경우 비밀번호 재설정 후 이용해주세요)')
            return redirect(url_for('login'))
        session['uid'] = user.id
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        pw = request.form.get('password','')
        agree_terms = request.form.get('agree_terms')
        agree_privacy = request.form.get('agree_privacy')
        if not email.endswith('@bl-m.kr'):
            flash('학교 이메일(@bl-m.kr)만 가입할 수 있습니다.')
            return redirect(url_for('signup'))
        if not (agree_terms and agree_privacy):
            flash('약관 및 개인정보처리방침에 동의해야 가입할 수 있습니다.')
            return redirect(url_for('signup'))
        exists = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if exists:
            flash('이미 가입된 이메일입니다.')
            return redirect(url_for('login'))
        user = User(email=email, pw_hash=generate_password_hash(pw))
        db.session.add(user)
        db.session.commit()
        session['uid'] = user.id
        return redirect(url_for('index'))
    # Pass summary text into template so it's visible inline
    return render_template('signup.html', TERMS="""본 서비스는 교육 목적의 위키입니다. 사용자는 다음을 준수합니다.
1) 타인의 권리를 침해하지 않습니다.
2) 법령과 학교 규정을 준수합니다.
3) 관리자가 판단할 경우 문서를 수정/삭제할 수 있습니다.
""".strip(), PRIVACY="""수집 항목: 학교 이메일(@bl-m.kr), 비밀번호(해시 처리), 로그인/문서 활동 로그
이용 목적: 사용자 인증, 서비스 운영 기록 관리
보관 및 파기: 회원 탈퇴 즉시 정보를 삭제하며, 법령상 보관이 필요한 로그는 해당 기간 보관 후 파기합니다.
제3자 제공/국외이전: 하지 않습니다.
정보주체 권리: 열람·정정·삭제·처리정지 요구 및 동의 철회 가능
보호 조치: 비밀번호는 평문이 아닌 해시로 저장하며, 최소 권한 원칙으로 접근을 통제합니다.
""".strip())

@app.route('/account/delete', methods=['POST'])
def delete_account():
    if not g.user: 
        abort(403)
    db.session.delete(g.user)
    db.session.commit()
    session.clear()
    return ('', 204)

@app.route('/docs')
def list_documents():
    docs = db.session.execute(select(Document).order_by(Document.title.asc())).scalars().all()
    return render_template('docs_list.html', docs=docs)

@app.route('/docs/new', methods=['GET','POST'])
def new_document():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        content = request.form.get('content','')
        if not title:
            flash('제목은 필수입니다.')
            return redirect(url_for('new_document'))
        d = Document(title=title, content=content, is_system=False)
        db.session.add(d)
        db.session.commit()
        return redirect(url_for('view_document', doc_id=d.id))
    return render_template('new_doc.html')

@app.route('/doc/<int:doc_id>')
def view_document(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    return render_template('doc.html', doc=doc)

@app.route('/d/<path:title>')
def doc_by_title(title):
    doc = db.session.execute(select(Document).where(Document.title == title)).scalar_one_or_none() or abort(404)
    return render_template('doc.html', doc=doc)

if __name__ == '__main__':
    app.run(debug=True)
