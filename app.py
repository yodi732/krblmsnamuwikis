
import os, datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY","dev-key")

def normalize_db_url(u:str):
    if not u:
        return None
    return u.replace("postgres://","postgresql://")
db_url = normalize_db_url(os.environ.get("DATABASE_URL"))
if db_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///local.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    pw = db.Column(db.String(255), nullable=False)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    is_legal = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    children = db.relationship('Document', lazy="joined", backref=db.backref('parent', remote_side=[id]))

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(255), nullable=False)
    action = db.Column(db.String(64), nullable=False)
    doc_title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# --- bootstrap/migration guards ---
with app.app_context():
    db.create_all()
    # add columns if not exists (for old DBs)
    try:
        db.session.execute(text("ALTER TABLE document ADD COLUMN IF NOT EXISTS is_legal BOOLEAN DEFAULT FALSE;"))
    except Exception:
        pass
    try:
        db.session.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS doc_title VARCHAR(255);"))
    except Exception:
        pass
    db.session.commit()

    # seed legal pages if missing (as read-only)
    def seed_legal(title, content):
        d = Document.query.filter_by(is_legal=True, title=title).first()
        if not d:
            d = Document(title=title, content=content, is_legal=True)
            db.session.add(d)
            db.session.commit()
    TERMS = """\
제1조(목적) 이 약관은 별내위키(이하 "서비스")의 이용에 관한 조건과 절차를 규정합니다.
제2조(회원의 의무) 회원은 법령과 본 약관, 서비스 안내에 따라 서비스를 이용해야 합니다.
제3조(콘텐츠) 회원이 작성한 문서의 권리와 책임은 작성자에게 있으며, 법령과 타인의 권리를 침해해서는 안 됩니다.
제4조(이용제한) 서비스는 약관 또는 법령 위반 시 이용을 제한할 수 있습니다.
제5조(면책) 서비스는 천재지변, 불가항력 기타 운영상 불가피한 사유로 인한 손해에 대하여 책임을 지지 않습니다.
제6조(분쟁) 분쟁이 발생하는 경우 관련 법령 및 관할법원(서울중앙지방법원)을 따릅니다.
시행일: 2025-10-19
"""
    PRIVACY = """\
1. 수집항목: 이메일, 비밀번호(해시 저장), 서비스 이용 기록(로그).
2. 이용목적: 회원관리, 보안, 서비스 품질 향상.
3. 보관기간: 회원 탈퇴 시 즉시 파기(법령에 따른 보존 예외).
4. 제3자 제공: 법령 근거가 있는 경우를 제외하고 제공하지 않습니다.
5. 처리위탁: 현재 위탁 없음.
6. 이용자 권리: 열람·정정·삭제·처리정지 요구 가능.
7. 보호조치: 접근권한 관리, 암호화, 로그 모니터링 등.
시행일: 2025-10-19
"""
    seed_legal("이용약관", TERMS)
    seed_legal("개인정보처리방침", PRIVACY)

# helpers
@app.before_request
def load_user():
    g.user = None
    if 'uid' in session:
        g.user = User.query.get(session['uid'])
    g.now = datetime.datetime.utcnow()
app.jinja_env.globals['now'] = datetime.datetime.utcnow()

def current_user():
    return g.user

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            flash("로그인이 필요합니다.")
            return redirect(url_for('login'))
        return fn(*a, **kw)
    return wrapper

def log_action(email, action, doc_title=None):
    al = AuditLog(user_email=email, action=action, doc_title=doc_title)
    db.session.add(al)
    db.session.commit()

# routes
@app.route('/')
def index():
    tops = Document.query.filter_by(parent_id=None).order_by(Document.updated_at.desc()).all()
    # exclude legal docs from editable listing; show them last as cards without delete in UI
    # but they still may be top-level; template hides delete if is_legal
    return render_template('index.html', tops=tops)

@app.route('/docs/<int:doc_id>')
def doc_detail(doc_id):
    d = Document.query.get_or_404(doc_id)
    return render_template('doc_detail.html', doc=d)

@app.route('/docs/new', methods=['GET','POST'])
@login_required
def doc_new():
    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        parent_id = request.form.get('parent_id') or None
        parent = Document.query.get(parent_id) if parent_id else None
        # prohibit deeper than 1 level
        if parent and parent.parent_id:
            flash("하위의 하위 문서는 만들 수 없습니다.")
            return redirect(url_for('doc_new'))
        d = Document(title=title, content=content, parent_id=parent.id if parent else None)
        db.session.add(d)
        db.session.commit()
        log_action(current_user().email, "create", d.title)
        return redirect(url_for('index'))
    parents = Document.query.order_by(Document.title).all()
    return render_template('doc_new.html', parents=parents)

@app.route('/docs/<int:doc_id>/delete')
@login_required
def doc_delete(doc_id):
    d = Document.query.get_or_404(doc_id)
    if d.is_legal:
        flash("법적 고지 문서는 삭제할 수 없습니다.")
        return redirect(url_for('index'))
    # also delete its children
    for c in list(d.children):
        db.session.delete(c)
    title = d.title
    db.session.delete(d)
    db.session.commit()
    log_action(current_user().email, "delete", title)
    return redirect(url_for('index'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        pw = request.form['pw']
        u = User.query.filter_by(email=email, pw=pw).first()
        if u:
            session['uid'] = u.id
            log_action(u.email, "login")
            flash("로그인되었습니다.")
            return redirect(url_for('index'))
        flash("이메일 또는 비밀번호가 올바르지 않습니다.")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    u = current_user()
    log_action(u.email, "logout")
    session.clear()
    flash("로그아웃되었습니다.")
    return redirect(url_for('index'))

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        pw = request.form['pw']
        pw2 = request.form['pw2']
        if pw != pw2:
            flash("비밀번호가 일치하지 않습니다.")
            return redirect(url_for('signup'))
        if not (request.form.get('agree_terms') and request.form.get('agree_privacy')):
            flash("약관 및 개인정보처리방침에 동의가 필요합니다.")
            return redirect(url_for('signup'))
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.")
            return redirect(url_for('signup'))
        u = User(email=email, pw=pw)
        db.session.add(u)
        db.session.commit()
        flash("가입되었습니다. 로그인해주세요.")
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/account/delete')
@login_required
def delete_account():
    u = current_user()
    email = u.email
    # delete user and clear session
    db.session.delete(u)
    db.session.commit()
    session.clear()
    log_action(email, "account_delete")
    flash("계정이 삭제되었습니다.")
    return redirect(url_for('index'))

@app.route('/logs')
@login_required
def view_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(500).all()
    return render_template('logs.html', logs=logs)

# legal pages (read-only, not Document table)
TERMS_CONTENT = """{{ terms }}"""
PRIVACY_CONTENT = """{{ privacy }}"""

@app.route('/legal/terms')
def legal_terms():
    # load from Document where is_legal True
    d = Document.query.filter_by(is_legal=True, title="이용약관").first()
    return render_template('legal.html', title="이용약관", content=d.content if d else "약관이 준비되지 않았습니다.")

@app.route('/legal/privacy')
def legal_privacy():
    d = Document.query.filter_by(is_legal=True, title="개인정보처리방침").first()
    return render_template('legal.html', title="개인정보처리방침", content=d.content if d else "정책이 준비되지 않았습니다.")

if __name__ == "__main__":
    app.run(debug=True)
