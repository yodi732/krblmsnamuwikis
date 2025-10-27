from flask import Flask, render_template, request, redirect, url_for, session, g, abort, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text, inspect
from datetime import datetime, timezone, timedelta
from flask import send_from_directory
from flask import Response
import os, json

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///local.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.getenv("SECRET_KEY", "dev-key")

KST = timezone(timedelta(hours=9))
@app.context_processor
def inject_now():
    return {"now": datetime.now(KST)}

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_system = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=True, index=True)
    parent = db.relationship("Document", remote_side=[id], backref=db.backref("children", lazy="dynamic"))

def safe_migrate():
    insp = inspect(db.engine)
    with db.engine.begin() as conn:
        if "document" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("document")]
            if "content" not in cols and "body" in cols:
                conn.execute(text("ALTER TABLE document RENAME COLUMN body TO content"))
        if "user" in insp.get_table_names():
            ucols = [c["name"] for c in insp.get_columns("user")]
            if "is_admin" not in ucols:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE'))
        if "document" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("document")]
            if "parent_id" not in cols:
                try:
                    conn.execute(text('ALTER TABLE "document" ADD COLUMN parent_id INTEGER'))
                except Exception:
                    pass
    db.create_all()

AUDIT_LOG = os.path.join(os.path.dirname(__file__), "audit.log")
def write_audit(action, user_email, doc_id=None, title=None):
    try:
        rec = {"ts": datetime.utcnow().isoformat(timespec="seconds")+"Z","user":user_email,"action":action,"doc_id":doc_id,"title":title}
        with open(AUDIT_LOG, "a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False)+"\n")
    except: pass

@app.before_request
def load_user():
    g.user=None
    uid=session.get("user_id")
    if uid: g.user=db.session.get(User, uid)

def _parents():
    return Document.query.filter_by(is_system=False).order_by(Document.created_at.desc()).all()

@app.route("/")
def index():
    docs=Document.query.filter_by(is_system=False).order_by(Document.created_at.desc()).all()
    return render_template("index.html", docs=docs)

@app.route("/home")
def home():
    roots=Document.query.filter_by(parent_id=None, is_system=False).order_by(Document.created_at.desc()).all()
    return render_template("home.html", roots=roots, doc_model=Document)

@app.route("/document/<int:doc_id>")
def view_document(doc_id):
    doc=db.session.get(Document, doc_id) or abort(404)
    children=doc.children.order_by(Document.created_at.desc()).all()
    return render_template("document_view.html", doc=doc, children=children)

@app.route("/document/new", methods=["GET","POST"])
def create_document():
    if not g.user: return redirect(url_for("login"))
    parent_id=request.args.get("parent_id", type=int)
    parent=db.session.get(Document, parent_id) if parent_id else None
    if request.method=="POST":
        mode=request.form.get("mode")
        selected_parent_id=request.form.get("parent_id", type=int)
        title=request.form.get("title","").strip()
        content=request.form.get("content","").strip()
        if not title or not content:
            return render_template("document_edit.html", doc=None, parent=parent, mode=mode, parents=_parents(), error="제목/내용은 필수입니다.")
        pid=None
        if mode=="child":
            pid=selected_parent_id or (parent.id if parent else None)
        doc=Document(title=title, content=content, is_system=False, parent_id=pid)
        db.session.add(doc); db.session.commit()
        write_audit("create", g.user.email, doc.id, doc.title)
        return redirect(url_for("view_document", doc_id=doc.id))
    return render_template("document_edit.html", doc=None, parent=parent, mode=("child" if parent else "parent"), parents=_parents())

@app.route("/document/<int:doc_id>/edit", methods=["GET","POST"])
def edit_document(doc_id):
    if not g.user: return redirect(url_for("login"))
    doc=db.session.get(Document, doc_id) or abort(404)
    if doc.is_system: abort(403)
    if request.method=="POST":
        doc.title=request.form.get("title","").strip()
        doc.content=request.form.get("content","").strip()
        mode=request.form.get("mode")
        selected_parent_id=request.form.get("parent_id", type=int)
        if mode=="parent": doc.parent_id=None
        elif mode=="child": doc.parent_id=selected_parent_id if selected_parent_id else None
        db.session.commit()
        write_audit("update", g.user.email, doc.id, doc.title)
        return redirect(url_for("view_document", doc_id=doc.id))
    return render_template("document_edit.html", doc=doc, parent=doc.parent, mode=("child" if doc.parent_id else "parent"), parents=_parents())

@app.route("/document/<int:doc_id>/delete", methods=["POST"])
def delete_document(doc_id):
    if not g.user: abort(403)
    doc=db.session.get(Document, doc_id) or abort(404)
    if doc.is_system: 
        flash("시스템 문서는 삭제할 수 없습니다.","warning")
        return redirect(url_for("index"))
    title=doc.title
    def wipe(d):
        for c in d.children.all(): wipe(c)
        db.session.delete(d)
    wipe(doc); db.session.commit()
    write_audit("delete", g.user.email, doc_id, title)
    flash("문서를 삭제했습니다.","success")
    return redirect(url_for("index"))

@app.route("/logs")
def logs():
    if not g.user: abort(403)
    rows=[]
    if os.path.exists(AUDIT_LOG):
        with open(AUDIT_LOG,"r",encoding="utf-8") as f:
            for line in f:
                try: rows.append(json.loads(line))
                except: pass
    rows.reverse()
    return render_template("logs.html", rows=rows)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        pw=request.form.get("password","")
        user=User.query.filter(db.func.lower(User.email)==email).first()
        if user and check_password_hash(user.password_hash,pw):
            session["user_id"]=user.id; return redirect(url_for("index"))
        return render_template("login.html", error="이메일 또는 비밀번호가 올바르지 않습니다.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("index"))

TERMS_PATH=os.path.join(os.path.dirname(__file__),"terms.txt")
PRIVACY_PATH=os.path.join(os.path.dirname(__file__),"privacy.txt")
def load_text_file(p):
    return open(p,"r",encoding="utf-8").read() if os.path.exists(p) else ""

@app.route("/signup", methods=["GET","POST"])
def signup():
    terms_text=load_text_file(TERMS_PATH) or "여기에 서비스 이용약관 전문을 넣으세요."
    privacy_text=load_text_file(PRIVACY_PATH) or "여기에 개인정보처리방침 전문을 넣으세요."
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        pw=request.form.get("password","")
        pw2=request.form.get("password2","")
        agree_terms=request.form.get("agree_terms")=="on"
        agree_priv=request.form.get("agree_priv")=="on"
        if not agree_terms or not agree_priv:
            return render_template("signup.html", error="약관/개인정보에 동의해 주세요.", terms_text=terms_text, privacy_text=privacy_text)
        if not email.endswith("@bl-m.kr"):
            return render_template("signup.html", error="학교 계정(@bl-m.kr)만 가입 가능합니다.", terms_text=terms_text, privacy_text=privacy_text)
        if pw!=pw2:
            return render_template("signup.html", error="비밀번호가 일치하지 않습니다.", terms_text=terms_text, privacy_text=privacy_text)
        if User.query.filter(db.func.lower(User.email)==email).first():
            return render_template("signup.html", error="이미 가입된 이메일입니다.", terms_text=terms_text, privacy_text=privacy_text)
        user=User(email=email, password_hash=generate_password_hash(pw), is_admin=False)
        db.session.add(user); db.session.commit()
        session["user_id"]=user.id; write_audit("create_user", user.email)
        return redirect(url_for("index"))
    return render_template("signup.html", terms_text=terms_text, privacy_text=privacy_text)

@app.route("/account/delete", methods=["GET","POST"])
def account_delete():
    if not g.user: return redirect(url_for("login"))
    if request.method=="POST":
        pw=request.form.get("password","")
        if not check_password_hash(g.user.password_hash,pw):
            return render_template("account_delete.html", error="비밀번호가 일치하지 않습니다.")
        u_email=g.user.email; u=g.user; session.clear(); db.session.delete(u); db.session.commit()
        write_audit("delete_user", u_email); flash("회원 탈퇴가 완료되었습니다.","success")
        return redirect(url_for("index"))
    return render_template("account_delete.html")

@app.route("/legal/terms")
def terms(): return render_template("legal_terms.html", content=load_text_file(TERMS_PATH) or "여기에 서비스 이용약관 전문을 넣으세요.")
@app.route("/legal/privacy")
def privacy(): return render_template("legal_privacy.html", content=load_text_file(PRIVACY_PATH) or "여기에 개인정보처리방침 전문을 넣으세요.")

@app.route("/static/<path:filename>")
def static_files(filename): return send_from_directory(os.path.join(app.root_path, "static"), filename)

@app.route('/googlefb8d25750b3e6720.html')
def google_verification():
    return send_from_directory('.', 'googlefb8d25750b3e6720.html')

@app.route('/sitemap.xml')
def sitemap():
    pages = [
        'https://krblmsnamuwikis.onrender.com/',
        'https://krblmsnamuwikis.onrender.com/login',
        'https://krblmsnamuwikis.onrender.com/register',
        'https://krblmsnamuwikis.onrender.com/docs',
        'https://krblmsnamuwikis.onrender.com/privacy',
        'https://krblmsnamuwikis.onrender.com/terms'
    ]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in pages:
        xml.append(f"<url><loc>{page}</loc></url>")
    xml.append('</urlset>')
    return Response('\n'.join(xml), mimetype='application/xml')

from flask import make_response

@app.route('/robots.txt')
def robots_txt():
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Sitemap: https://krblmsnamuwikis.onrender.com/sitemap.xml\n"
    )
    resp = make_response(content, 200)
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp

NAVER_VERIFY_FILE = "naver34060f97d428ade4705f6c37cbaf8f5a.html"

@app.route(f"/{NAVER_VERIFY_FILE}")
def naver_verify():
    return send_from_directory(
        directory=os.path.abspath(os.path.dirname(__file__)),
        path=NAVER_VERIFY_FILE,
        mimetype="text/html"
    )

with app.app_context(): safe_migrate()
if __name__=="__main__": app.run(debug=True)
