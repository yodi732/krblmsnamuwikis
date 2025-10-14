
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app.db")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-" + os.urandom(8).hex())

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, pw: str):
        self.password_hash = generate_password_hash(pw, method="pbkdf2:sha256", salt_length=16)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    parent_id = db.Column(db.Integer, nullable=True)
    author_email = db.Column(db.String(255), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route("/")
def index():
    docs = Document.query.order_by(Document.created_at.desc()).all()
    return render_template("index.html", title="별내위키", docs=docs)

@app.route("/privacy")
def privacy():
    return render_template("privacy.html", title="개인정보처리방침")

@app.route("/terms")
def terms():
    return render_template("terms.html", title="이용약관")

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            error = "이메일 또는 비밀번호가 올바르지 않습니다."
        else:
            login_user(user)
            return redirect(url_for("index"))
    return render_template("login.html", error=error, title="로그인")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/register", methods=["GET","POST"])
def register():
    error = None
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        agree = request.form.get("agree")
        if not agree:
            error = "약관에 동의해 주세요."
        elif not email:
            error = "이메일을 입력해 주세요."
        elif not password or len(password) < 6:
            error = "비밀번호는 6자 이상이어야 합니다."
        else:
            ex = User.query.filter_by(email=email).first()
            if ex:
                error = "이미 가입된 이메일입니다."
            else:
                u = User(email=email)
                u.set_password(password)
                db.session.add(u)
                db.session.commit()
                login_user(u)
                return redirect(url_for("index"))
    return render_template("register.html", error=error, title="회원가입")

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
