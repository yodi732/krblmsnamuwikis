from flask import Flask, render_template, request, redirect, url_for, session, g, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
# Secret key & DB URL should come from environment in production
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///local.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ----------------------
# Models
# ----------------------

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)

    # The column your DB actually enforces as NOT NULL
    password_hash = db.Column(db.Text, nullable=False)

    # Legacy/plaintext column that may exist in your DB. Keep nullable and unused.
    pw = db.Column(db.Text, nullable=True)

    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_reason = db.Column(db.Text, nullable=True)

    # Helpers
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
        # Do not store plaintext even if column exists
        self.pw = None

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)

    # DB column is content (NOT body). Keep canonical storage here...
    content = db.Column("content", db.Text, nullable=False)

    # ...but continue to allow 'body' attribute access for existing templates/code.
    from sqlalchemy.orm import synonym
    body = synonym("content")

    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

# ----------------------
# Hooks
# ----------------------
@app.before_request
def load_user():
    uid = session.get("uid")
    g.user = User.query.get(uid) if uid else None

# ----------------------
# Routes
# ----------------------

@app.get("/")
def index():
    # Exclude system docs (e.g., Terms/Privacy) from list
    docs = Document.query.filter_by(is_system=False).order_by(Document.created_at.desc()).all()
    # Minimal inline template fallback if project templates are not shipped in patch
    # You can remove this block if your project uses separate templates.
    return (
        "<h1>별내위키</h1>"
        + "".join(f"<div><a href='/doc/{d.id}'>{d.title}</a></div>" for d in docs)
        + "<footer style='margin-top:2rem;font-size:12px;color:#777'>"
          "<a href='/legal/terms'>이용약관</a> · <a href='/legal/privacy'>개인정보처리방침</a>"
          "</footer>"
    )

@app.get("/doc/<int:doc_id>")
def view_doc(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.is_system:
        abort(404)
    return f"<h1>{doc.title}</h1><div>{doc.body}</div>"

# ---- Auth ----

@app.get("/login")
def login_form():
    return (
        "<h2>로그인</h2>"
        "<form method='post'>"
        "<input name='email' placeholder='email'><br>"
        "<input name='password' placeholder='password' type='password'><br>"
        "<button type='submit'>로그인</button>"
        "</form>"
        "<div style='margin-top:8px'><a href='/signup'>회원가입</a></div>"
        "<footer style='margin-top:2rem;font-size:12px;color:#777'>"
        "<a href='/legal/terms'>이용약관</a> · <a href='/legal/privacy'>개인정보처리방침</a>"
        "</footer>"
    )

@app.post("/login")
def login_submit():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return (
            "<h2>로그인</h2>"
            "<p style='color:red'>이메일 또는 비밀번호가 올바르지 않습니다.</p>"
            "<a href='/login'>돌아가기</a>"
        )

    session["uid"] = user.id
    return redirect(url_for("index"))

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.get("/signup")
def signup_form():
    # No marketing/ads consent toggles (per user's requirement)
    return (
        "<h2>회원가입</h2>"
        "<form method='post'>"
        "<input name='email' placeholder='email'><br>"
        "<input name='password' placeholder='password' type='password'><br>"
        "<button type='submit'>가입</button>"
        "</form>"
        "<p style='font-size:12px;color:#777'>가입 시 "
        "<a href='/legal/terms'>이용약관</a> 및 "
        "<a href='/legal/privacy'>개인정보처리방침</a>에 동의하게 됩니다. "
        "전문은 링크를 통해서만 열람 가능하며 문서 목록에는 표시되지 않습니다.</p>"
    )

@app.post("/signup")
def signup_submit():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return (
            "<h2>회원가입</h2>"
            "<p style='color:red'>이메일과 비밀번호를 입력하세요.</p>"
            "<a href='/signup'>돌아가기</a>"
        )

    existing = User.query.filter_by(email=email).first()
    if existing:
        return (
            "<h2>회원가입</h2>"
            "<p style='color:red'>이미 가입된 이메일입니다.</p>"
            "<a href='/login'>로그인하기</a>"
        )

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    session["uid"] = user.id
    return redirect(url_for("index"))

# ---- Legal: view-only, not listed, and not editable ----
@app.get("/legal/terms")
def terms():
    # Fixed view-only content (could also be served from templates/static file)
    title = "이용약관 (별내위키)"
    body = (
        "<p>이 문서는 보기 전용이며 문서 목록에 표시되지 않습니다. "
        "서비스 이용에 관한 기본 조건을 규정합니다.</p>"
        "<ul>"
        "<li>서비스 명칭: 별내위키</li>"
        "<li>콘텐츠 라이선스: 이용자가 작성한 콘텐츠는 이용자에게 귀속됩니다.</li>"
        "<li>금지행위: 불법, 권리침해, 스팸성 활동 등</li>"
        "<li>면책: 가능한 한 안정적으로 제공하나, 중단·변경될 수 있습니다.</li>"
        "</ul>"
    )
    return f"<h1>{title}</h1><div>{body}</div>"

@app.get("/legal/privacy")
def privacy():
    title = "개인정보처리방침 (별내위키)"
    body = (
        "<p>이 문서는 보기 전용이며 문서 목록에 표시되지 않습니다.</p>"
        "<ul>"
        "<li>수집항목: 이메일, 비밀번호 해시</li>"
        "<li>보관기간: 탈퇴 시 즉시 삭제(관계 법령 예외 제외)</li>"
        "<li>처리위탁/제3자 제공: 없음(호스팅/인프라 제공자 제외)</li>"
        "<li>권리: 열람, 정정, 삭제, 처리정지 요구 가능</li>"
        "</ul>"
    )
    return f"<h1>{title}</h1><div>{body}</div>"

# Healthcheck
@app.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}

# WSGI entry
app = app

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)