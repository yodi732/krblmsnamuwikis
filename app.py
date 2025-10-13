
import os, re, secrets, datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, current_user, login_required, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
db_url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///local.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://") and "+psycopg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, default=True)
    agreed_at = db.Column(db.DateTime)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    fail_count = db.Column(db.Integer, default=0)
    last_fail_date = db.Column(db.Date)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(255), nullable=False)
    actor_email = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))

def run_bootstrap_migrations():
    with db.engine.begin() as conn:
        db.metadata.create_all(bind=conn)
        # Add author_id if missing
        try:
            conn.execute(text("""
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='document' AND column_name='author_id'
                  ) THEN
                    ALTER TABLE public.document ADD COLUMN author_id INTEGER NULL;
                    BEGIN
                      ALTER TABLE public.document
                        ADD CONSTRAINT document_author_id_fkey
                        FOREIGN KEY (author_id) REFERENCES public."user"(id) ON DELETE SET NULL;
                    EXCEPTION WHEN duplicate_object THEN NULL;
                    END;
                  END IF;
                END$$;
            """))
        except Exception:
            # likely SQLite or permission; ignore
            pass
        # Add created_at if missing
        try:
            conn.execute(text("""
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='document' AND column_name='created_at'
                  ) THEN
                    ALTER TABLE public.document ADD COLUMN created_at TIMESTAMP NULL DEFAULT now();
                  END IF;
                END$$;
            """))
        except Exception:
            pass

@app.before_first_request
def init():
    try:
        run_bootstrap_migrations()
    except Exception:
        db.create_all()

ALLOWED_DOMAIN = "@bl-m.kr"
def is_school_email(email:str)->bool:
    return isinstance(email, str) and email.endswith(ALLOWED_DOMAIN) and re.match(r"^[A-Za-z0-9._%+-]+@bl-m\.kr$", email) is not None

def log(action:str):
    db.session.add(Log(action=action, actor_email=(current_user.email if current_user.is_authenticated else None)))
    db.session.commit()

@app.route("/")
def index():
    parents = (Document.query
               .filter(Document.parent_id.is_(None))
               .order_by(Document.created_at.desc())
               .all())
    children_map = {}
    if parents:
        pids = [p.id for p in parents]
        childs = (Document.query
                  .filter(Document.parent_id.in_(pids))
                  .order_by(Document.created_at.desc())
                  .all())
        for c in childs:
            children_map.setdefault(c.parent_id, []).append(c)
    uid_set = set([d.author_id for d in parents if d.author_id] + [c.author_id for lst in children_map.values() for c in lst if c.author_id])
    email_map = {}
    if uid_set:
        users = User.query.filter(User.id.in_(uid_set)).all()
        email_map = {u.id: u.email for u in users}
    for d in parents:
        d.author_email = email_map.get(d.author_id)
    for lst in children_map.values():
        for c in lst:
            c.author_email = email_map.get(c.author_id)
    return render_template("index.html", parents=parents, children=children_map)

@app.route("/create", methods=["GET","POST"])
@login_required
def create():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        parent_id = request.form.get("parent_id") or None
        if not title or not content:
            flash("제목과 내용을 입력하세요.")
            return redirect(url_for("create"))
        if parent_id:
            parent = db.session.get(Document, int(parent_id))
            if not parent or parent.parent_id is not None:
                flash("하위의 하위 문서는 만들 수 없습니다.")
                return redirect(url_for("create"))
        doc = Document(title=title, content=content, parent_id=(int(parent_id) if parent_id else None), author_id=current_user.id)
        db.session.add(doc)
        db.session.commit()
        log(f"문서 생성: {title}")
        return redirect(url_for("index"))
    parents = Document.query.filter(Document.parent_id.is_(None)).order_by(Document.created_at.desc()).all()
    return render_template("create.html", parents=parents)

@app.route("/edit/<int:doc_id>", methods=["GET","POST"])
@login_required
def edit(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        if not title or not content:
            flash("제목과 내용을 입력하세요.")
            return redirect(url_for("edit", doc_id=doc_id))
        doc.title = title
        doc.content = content
        db.session.commit()
        log(f"문서 수정: {title}")
        return redirect(url_for("index"))
    return render_template("edit.html", doc=doc)

@app.route("/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    title = doc.title
    Document.query.filter_by(parent_id=doc.id).delete()
    db.session.delete(doc)
    db.session.commit()
    log(f"문서 삭제: {title}")
    return redirect(url_for("index"))

@app.route("/logs")
@login_required
def logs():
    logs = Log.query.order_by(Log.created_at.desc()).limit(200).all()
    return render_template("logs.html", logs=logs)

@app.route("/delete-account", methods=["GET","POST"])
@login_required
def delete_account():
    if request.method == "POST":
        pw = request.form.get("password","")
        if not check_password_hash(current_user.password, pw):
            flash("비밀번호가 올바르지 않습니다.")
            return redirect(url_for("delete_account"))
        db.session.execute(text("UPDATE document SET author_id=NULL WHERE author_id=:uid"), {"uid": current_user.id})
        uid = current_user.id
        logout_user()
        db.session.execute(text('DELETE FROM "user" WHERE id=:uid'), {"uid": uid})
        db.session.commit()
        flash("회원 탈퇴가 완료되었습니다.")
        return redirect(url_for("index"))
    return render_template("delete_account.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not is_school_email(email):
            flash("학교 이메일(@bl-m.kr)만 로그인할 수 있습니다.")
            return redirect(url_for("login"))
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("가입되지 않은 이메일입니다.")
            return redirect(url_for("login"))
        today = datetime.date.today()
        if user.last_fail_date != today:
            user.last_fail_date = today
            user.fail_count = 0
            db.session.commit()
        if user.fail_count >= 10:
            flash("로그인 실패가 오늘 10회를 초과했습니다. 내일 다시 시도하세요.")
            return redirect(url_for("login"))
        if not check_password_hash(user.password, password):
            user.fail_count += 1
            user.last_fail_date = today
            db.session.commit()
            flash("이메일 또는 비밀번호가 올바르지 않습니다.")
            return redirect(url_for("login"))
        login_user(user)
        flash("로그인 되었습니다.")
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
    flash("로그아웃 되었습니다.")
    return redirect(url_for("index"))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        agree = request.form.get("agree")
        if not agree:
            flash("약관 및 방침에 동의해야 가입할 수 있습니다.")
            return redirect(url_for("register"))
        if not is_school_email(email):
            flash("학교 이메일(@bl-m.kr)만 가입할 수 있습니다.")
            return redirect(url_for("register"))
        if User.query.filter_by(email=email).first():
            flash("이미 등록된 이메일입니다.")
            return redirect(url_for("register"))
        user = User(email=email, password=generate_password_hash(password), agreed_at=datetime.datetime.utcnow())
        db.session.add(user)
        db.session.commit()
        flash("가입이 완료되었습니다. 로그인하세요.")
        return redirect(url_for("login"))
    return render_template("register.html")

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

@app.route("/forgot", methods=["GET","POST"])
def forgot():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        if not is_school_email(email):
            flash("학교 이메일만 가능합니다.")
            return redirect(url_for("forgot"))
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("가입된 이메일이 없습니다.")
            return redirect(url_for("forgot"))
        token = serializer.dumps(email, salt="pw-reset")
        reset_url = url_for("reset", token=token, _external=True)
        flash(f"재설정 링크(모의): {reset_url}")
        return redirect(url_for("login"))
    return render_template("forgot.html")

@app.route("/reset/<token>", methods=["GET","POST"])
def reset(token):
    try:
        email = serializer.loads(token, salt="pw-reset", max_age=3600)
    except (BadSignature, SignatureExpired):
        flash("링크가 유효하지 않습니다.")
        return redirect(url_for("login"))
    user = User.query.filter_by(email=email).first() or abort(404)
    if request.method == "POST":
        pw = request.form.get("password","")
        user.password = generate_password_hash(pw)
        db.session.commit()
        flash("비밀번호가 변경되었습니다. 로그인하세요.")
        return redirect(url_for("login"))
    return render_template("reset.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

if __name__ == "__main__":
    app.run(debug=True)
