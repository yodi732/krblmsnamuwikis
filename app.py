import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
DB_PATH = 'wiki.db'

def init_db():
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

@app.route('/')
def index():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM categories ORDER BY name")
        categories = cur.fetchall()
    return render_template('index.html', categories=categories)

@app.route('/category/<int:cat_id>')
def view_category(cat_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM categories WHERE id=?", (cat_id,))
        cat = cur.fetchone()
        cur.execute("SELECT id, title FROM pages WHERE category_id=? ORDER BY title", (cat_id,))
        pages = cur.fetchall()
    return render_template('category.html', cat_id=cat_id, category=cat, pages=pages)

@app.route('/wiki/<int:page_id>')
def view_page(page_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT title, content FROM pages WHERE id=?", (page_id,))
        page = cur.fetchone()
    if not page:
        return "문서를 찾을 수 없습니다.", 404
    return render_template('view.html', page_id=page_id, title=page[0], content=page[1])

@app.route('/edit_page/<int:cat_id>/<int:page_id>', methods=['GET','POST'])
def edit_page(cat_id, page_id):
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            if page_id == 0:  # 새 문서
                cur.execute("INSERT INTO pages (category_id, title, content) VALUES (?,?,?)",
                            (cat_id, title, content))
            else:  # 기존 문서 수정
                cur.execute("UPDATE pages SET title=?, content=? WHERE id=?", (title, content, page_id))
            conn.commit()
        return redirect(url_for('view_category', cat_id=cat_id))

    page = None
    if page_id != 0:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT title, content FROM pages WHERE id=?", (page_id,))
            page = cur.fetchone()
    return render_template('edit_page.html', cat_id=cat_id, page_id=page_id, page=page)

@app.route('/delete_page/<int:page_id>')
def delete_page(page_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM pages WHERE id=?", (page_id,))
        conn.commit()
    return redirect(url_for('index'))

@app.route('/edit_category/<int:cat_id>', methods=['GET','POST'])
def edit_category(cat_id):
    if request.method == 'POST':
        name = request.form['name']
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            if cat_id == 0:
                cur.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            else:
                cur.execute("UPDATE categories SET name=? WHERE id=?", (name, cat_id))
            conn.commit()
        return redirect(url_for('index'))
    category = None
    if cat_id != 0:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM categories WHERE id=?", (cat_id,))
            category = cur.fetchone()
    return render_template('edit_category.html', cat_id=cat_id, category=category)

@app.route('/delete_category/<int:cat_id>')
def delete_category(cat_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM pages WHERE category_id=?", (cat_id,))
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.commit()
    return redirect(url_for('index'))

if __name__ == "__main__":
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
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
