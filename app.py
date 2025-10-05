from flask import Flask, render_template, request, redirect, url_for, flash, g
import sqlite3, os, markdown
from markupsafe import escape

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "wiki.db")

app = Flask(__name__)
app.secret_key = "change-me-to-secure-value"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        title TEXT NOT NULL,
        content TEXT DEFAULT '',
        FOREIGN KEY(category_id) REFERENCES categories(id)
    );
    """)
    db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

@app.before_first_request
def setup():
    init_db()

# Home: list categories
@app.route("/")
def index():
    db = get_db()
    cur = db.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cur.fetchall()
    return render_template("index.html", categories=categories)

# Create category
@app.route("/category/new", methods=["GET","POST"])
def new_category():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        if not name:
            flash("목차 이름을 입력하세요.")
            return redirect(url_for("new_category"))
        db = get_db()
        try:
            db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            db.commit()
            flash("목차가 생성되었습니다.")
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            flash("같은 이름의 목차가 이미 존재합니다.")
            return redirect(url_for("new_category"))
    return render_template("edit_category.html", category=None)

# Edit category
@app.route("/category/edit/<int:cid>", methods=["GET","POST"])
def edit_category(cid):
    db = get_db()
    cur = db.execute("SELECT id, name FROM categories WHERE id=?", (cid,))
    cat = cur.fetchone()
    if not cat:
        flash("목차를 찾을 수 없습니다.")
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name","").strip()
        if not name:
            flash("이름을 입력하세요.")
            return redirect(url_for("edit_category", cid=cid))
        try:
            db.execute("UPDATE categories SET name=? WHERE id=?", (name, cid))
            db.commit()
            flash("목차 이름이 변경되었습니다.")
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            flash("같은 이름의 목차가 이미 존재합니다.")
            return redirect(url_for("edit_category", cid=cid))
    return render_template("edit_category.html", category=cat)

# Delete category (and its pages)
@app.route("/category/delete/<int:cid>", methods=["POST"])
def delete_category(cid):
    db = get_db()
    db.execute("DELETE FROM pages WHERE category_id=?", (cid,))
    db.execute("DELETE FROM categories WHERE id=?", (cid,))
    db.commit()
    flash("목차와 하위 문서들이 삭제되었습니다.")
    return redirect(url_for("index"))

# Show category pages
@app.route("/category/<int:cid>")
def show_category(cid):
    db = get_db()
    cur = db.execute("SELECT id, name FROM categories WHERE id=?", (cid,))
    cat = cur.fetchone()
    if not cat:
        flash("목차를 찾을 수 없습니다.")
        return redirect(url_for("index"))
    cur = db.execute("SELECT id, title FROM pages WHERE category_id=? ORDER BY title", (cid,))
    pages = cur.fetchall()
    return render_template("category.html", category=cat, pages=pages)

# New page under category
@app.route("/category/<int:cid>/new", methods=["GET","POST"])
def new_page(cid):
    db = get_db()
    cur = db.execute("SELECT id, name FROM categories WHERE id=?", (cid,))
    cat = cur.fetchone()
    if not cat:
        flash("목차가 존재하지 않습니다.")
        return redirect(url_for("index"))
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        if not title:
            flash("문서 제목을 입력하세요.")
            return redirect(url_for("new_page", cid=cid))
        db.execute("INSERT INTO pages (category_id, title, content) VALUES (?,?,?)", (cid, title, content))
        db.commit()
        flash("문서가 생성되었습니다.")
        # get new page id
        cur = db.execute("SELECT id FROM pages WHERE category_id=? AND title=? ORDER BY id DESC LIMIT 1", (cid, title))
        newp = cur.fetchone()
        return redirect(url_for("view_page", pid=newp["id"]))
    return render_template("edit.html", page=None, category=cat)

# View page
@app.route("/wiki/<int:pid>")
def view_page(pid):
    db = get_db()
    cur = db.execute("SELECT p.id, p.title, p.content, c.id as cid, c.name as cname FROM pages p LEFT JOIN categories c ON p.category_id=c.id WHERE p.id=?", (pid,))
    p = cur.fetchone()
    if not p:
        flash("문서를 찾을 수 없습니다.")
        return redirect(url_for("index"))
    html = markdown.markdown(p["content"] or "")
    return render_template("page.html", page=p, html=html)

# Edit page (including changing title and category)
@app.route("/edit/<int:pid>", methods=["GET","POST"])
def edit_page(pid):
    db = get_db()
    cur = db.execute("SELECT id, category_id, title, content FROM pages WHERE id=?", (pid,))
    p = cur.fetchone()
    if not p:
        flash("문서를 찾을 수 없습니다.")
        return redirect(url_for("index"))
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","")
        new_cid = request.form.get("category_id")
        if not title:
            flash("문서 제목을 입력하세요.")
            return redirect(url_for("edit_page", pid=pid))
        # update
        db.execute("UPDATE pages SET title=?, content=?, category_id=? WHERE id=?", (title, content, new_cid, pid))
        db.commit()
        flash("문서가 저장되었습니다.")
        return redirect(url_for("view_page", pid=pid))
    # get categories for dropdown
    cur = db.execute("SELECT id, name FROM categories ORDER BY name")
    cats = cur.fetchall()
    return render_template("edit.html", page=p, categories=cats, category=None)

# Delete page
@app.route("/delete/<int:pid>", methods=["POST"])
def delete_page(pid):
    db = get_db()
    db.execute("DELETE FROM pages WHERE id=?", (pid,))
    db.commit()
    flash("문서가 삭제되었습니다.")
    return redirect(url_for("index"))

if __name__ == "__main__":
    # If running locally, create DB if not exists
    if not os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                FOREIGN KEY(category_id) REFERENCES categories(id)
            );
            """)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
