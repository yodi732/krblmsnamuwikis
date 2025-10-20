import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    else:
        db_url = 'sqlite:///byeollae.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db = SQLAlchemy(app)

    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(255), unique=True, nullable=False)
        password_hash = db.Column(db.String(255), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        agreed_tos = db.Column(db.Boolean, default=False, nullable=False)
        agreed_privacy = db.Column(db.Boolean, default=False, nullable=False)

        def set_password(self, pw):
            self.password_hash = generate_password_hash(pw)

        def check_password(self, pw):
            return check_password_hash(self.password_hash, pw)

    class Document(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(255), unique=True, nullable=False)
        content = db.Column(db.Text, default='', nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        is_system = db.Column(db.Boolean, default=False, nullable=False)
        parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
        parent = db.relationship('Document', remote_side=[id], backref='children')

    def current_user():
        uid = session.get('uid')
        if not uid:
            return None
        return db.session.get(User, uid)

    @app.before_request
    def ensure_db_and_seed():
        with app.app_context():
            db.create_all()
            tos = db.session.execute(db.select(Document).filter_by(title='이용약관')).scalar_one_or_none()
            if not tos:
                tos = Document(
                    title='이용약관',
                    content='''본 서비스는 교육 목적의 위키입니다. 사용자는 다음을 준수합니다.
1) 타인의 권리를 침해하지 않습니다.
2) 법령과 학교 규정을 준수합니다.
3) 관리자가 판단한 경우 문서를 수정/삭제할 수 있습니다.''',
                    is_system=True
                )
                db.session.add(tos)
            pp = db.session.execute(db.select(Document).filter_by(title='개인정보처리방침')).scalar_one_or_none()
            if not pp:
                pp = Document(
                    title='개인정보처리방침',
                    content='''개인정보처리방침(요약)
1. 수집 항목: 학교 이메일(@bl-m.kr), 비밀번호(해시), 로그인/문서 활동 로그
2. 이용 목적: 사용자 인증, 서비스 운영 기록 관리
3. 보관 및 파기: 회원 탈퇴 즉시 정보는 삭제하며, 법령상 보관이 필요한 로그는 해당 기간 보관 후 파기합니다.
4. 제3자 제공/국외이전: 하지 않습니다.
5. 정보주체 권리: 열람/정정/삭제/처리정지 요청 및 동의 철회 가능
6. 보호 조치: 비밀번호는 평문이 아닌 해시로 저장하며, 최소 권한 원칙으로 접근을 통제합니다.''',
                    is_system=True
                )
                db.session.add(pp)
            db.session.commit()

    @app.route('/')
    def home():
        docs = db.session.execute(db.select(Document).order_by(Document.updated_at.desc())).scalars().all()
        return render_template('home.html', docs=docs, me=current_user())

    @app.route('/docs')
    def docs_list():
        tops = db.session.execute(db.select(Document).filter_by(parent_id=None).order_by(Document.title)).scalars().all()
        return render_template('docs.html', docs=tops, me=current_user())

    @app.route('/docs/<title>')
    def doc_view(title):
        doc = db.session.execute(db.select(Document).filter_by(title=title)).scalar_one_or_none()
        if not doc:
            abort(404)
        kids = db.session.execute(db.select(Document).filter_by(parent_id=doc.id).order_by(Document.title)).scalars().all()
        return render_template('doc_view.html', doc=doc, kids=kids, me=current_user())

    @app.route('/create', methods=['GET','POST'])
    def create_doc():
        me = current_user()
        if not me:
            return redirect(url_for('login', next=url_for('create_doc')))
        if request.method == 'POST':
            title = request.form.get('title','').strip()
            content = request.form.get('content','').strip()
            parent_title = request.form.get('parent','').strip()
            parent = None
            if parent_title:
                parent = db.session.execute(db.select(Document).filter_by(title=parent_title)).scalar_one_or_none()
            if not title:
                flash('제목을 입력하세요.')
            else:
                exists = db.session.execute(db.select(Document).filter_by(title=title)).scalar_one_or_none()
                if exists:
                    flash('이미 존재하는 문서 제목입니다.')
                else:
                    d = Document(title=title, content=content, parent=parent)
                    db.session.add(d)
                    db.session.commit()
                    return redirect(url_for('doc_view', title=title))
        titles = db.session.execute(db.select(Document.title).order_by(Document.title)).scalars().all()
        return render_template('create.html', titles=titles, me=me)

    @app.route('/signup', methods=['GET','POST'])
    def signup():
        if request.method == 'POST':
            email = request.form.get('email','').strip()
            pw = request.form.get('password','')
            agree_tos = request.form.get('agree_tos') == 'on'
            agree_privacy = request.form.get('agree_privacy') == 'on'
            if not (agree_tos and agree_privacy):
                flash('약관과 개인정보처리방침에 동의해야 가입할 수 있습니다.')
                return redirect(url_for('signup'))
            if not email.endswith('@bl-m.kr'):
                flash('학교 이메일(@bl-m.kr)만 허용됩니다.')
                return redirect(url_for('signup'))
            if len(pw) < 6:
                flash('비밀번호는 6자 이상 입력하세요.')
                return redirect(url_for('signup'))
            dup = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
            if dup:
                flash('이미 가입된 이메일입니다.')
                return redirect(url_for('login'))
            u = User(email=email, agreed_tos=True, agreed_privacy=True)
            u.set_password(pw)
            db.session.add(u)
            db.session.commit()
            session['uid'] = u.id
            return redirect(url_for('home'))
        tos = db.session.execute(db.select(Document).filter_by(title='이용약관')).scalar_one()
        pp = db.session.execute(db.select(Document).filter_by(title='개인정보처리방침')).scalar_one()
        return render_template('signup.html', tos=tos, pp=pp, me=current_user())

    @app.route('/login', methods=['GET','POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email','').strip()
            pw = request.form.get('password','')
            user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
            if not user or not user.check_password(pw):
                flash('이메일 또는 비밀번호가 올바르지 않습니다.')
                return redirect(url_for('login'))
            session['uid'] = user.id
            nxt = request.args.get('next')
            return redirect(nxt or url_for('home'))
        return render_template('login.html', me=current_user())

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('home'))

    @app.route('/account/delete', methods=['POST'])
    def account_delete():
        me = current_user()
        if not me:
            return redirect(url_for('login'))
        db.session.delete(me)
        session.clear()
        db.session.commit()
        return redirect(url_for('home'))

    @app.route('/terms')
    def terms_full():
        tos = db.session.execute(db.select(Document).filter_by(title='이용약관')).scalar_one()
        return render_template('doc_view.html', doc=tos, kids=[], me=current_user())

    @app.route('/privacy')
    def privacy_full():
        pp = db.session.execute(db.select(Document).filter_by(title='개인정보처리방침')).scalar_one()
        return render_template('doc_view.html', doc=pp, kids=[], me=current_user())

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
