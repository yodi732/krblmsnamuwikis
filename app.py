from flask import Flask, render_template, request, redirect, url_for, session, g, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
from sqlalchemy.orm import synonym
from sqlalchemy import text, func

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///local.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ================== MODELS ==================
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    pw = db.Column(db.Text, nullable=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_reason = db.Column(db.Text, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
        self.pw = None

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Document(db.Model):
    __tablename__ = "document"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    # ✅ DB에는 content, 코드에서는 body
    body = db.Column("content", db.Text, nullable=False)
    content = synonym("body")
    is_system = db.Column(db.Boolean, nullable=False, server_default=text('false'))
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())

# ================== HOOK ==================
@app.before_request
def load_user():
    uid = session.get("uid")
    g.user = User.query.get(uid) if uid else None

# ================== ROUTES ==================
@app.get("/")
def index():
    docs = Document.query.filter_by(is_system=False).order_by(Document.created_at.desc()).all()
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

@app.get("/legal/terms")
def terms():
    return "<h1>이용약관 (별내위키)</h1><p>이 문서는 보기 전용이며 문서 목록에 표시되지 않습니다.</p>"

@app.get("/legal/privacy")
def privacy():
    return "<h1>개인정보처리방침 (별내위키)</h1><p>이 문서는 보기 전용이며 문서 목록에 표시되지 않습니다.</p>"

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)