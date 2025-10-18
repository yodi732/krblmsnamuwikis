import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text, func
from werkzeug.security import generate_password_hash, check_password_hash
import re
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "test_secret")
db = SQLAlchemy(app)

# 모델 정의
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, default="")
    slug = db.Column(db.String(255), unique=True, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"))
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "doc"

# 자동 스키마 보정
def ensure_schema_and_slugs():
    insp = inspect(db.engine)
    cols = [c["name"] for c in insp.get_columns("document")]
    if "slug" not in cols:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE document ADD COLUMN slug VARCHAR(255)"))

    with db.engine.begin() as conn:
        rows = conn.execute(text("SELECT id, title FROM document WHERE slug IS NULL OR slug = ''")).mappings().all()
        for r in rows:
            base = slugify(r["title"] or "")
            slug = base or f"doc-{r['id']}"
            i = 2
            while conn.execute(text("SELECT 1 FROM document WHERE slug = :s AND id <> :id LIMIT 1"), {"s": slug, "id": r["id"]}).scalar():
                slug = f"{base}-{i}"
                i += 1
            conn.execute(text("UPDATE document SET slug = :s WHERE id = :id"), {"s": slug, "id": r["id"]})

    idx = {ix["name"] for ix in insp.get_indexes("document")}
    if "ix_document_slug" not in idx:
        with db.engine.begin() as conn:
            conn.execute(text("CREATE UNIQUE INDEX ix_document_slug ON document(slug)"))

# 기본 페이지 생성
def ensure_terms_pages():
    now = datetime.utcnow()
    if not Document.query.filter_by(slug="terms").first():
        db.session.add(Document(title="이용약관", slug="terms", content="이용약관 내용", created_at=now, updated_at=now))
    if not Document.query.filter_by(slug="privacy").first():
        db.session.add(Document(title="개인정보처리방침", slug="privacy", content="개인정보처리방침 내용", created_at=now, updated_at=now))
    db.session.commit()

@app.route("/")
def index():
    docs = Document.query.all()
    return render_template("index.html", docs=docs)

@app.route("/view/<slug>")
def view(slug):
    doc = Document.query.filter_by(slug=slug).first_or_404()
    return render_template("view.html", doc=doc)

@app.route("/add", methods=["POST"])
def add():
    title = request.form["title"]
    content = request.form["content"]
    slug = slugify(title)
    now = datetime.utcnow()
    doc = Document(title=title, content=content, slug=slug, created_at=now, updated_at=now)
    db.session.add(doc)
    db.session.commit()
    return redirect(url_for("index"))

with app.app_context():
    db.create_all()
    ensure_schema_and_slugs()
    ensure_terms_pages()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
