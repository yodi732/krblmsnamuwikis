import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
DB_PATH = 'wiki.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            FOREIGN KEY(parent_id) REFERENCES pages(id)
        );
        """)

def get_page(page_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, parent_id, title, content FROM pages WHERE id=?", (page_id,))
        return cur.fetchone()

def get_children(parent_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, title FROM pages WHERE parent_id=? ORDER BY title", (parent_id,))
        return cur.fetchall()

@app.route('/')
def index():
    # 최상위 문서들 (목차)
    roots = get_children(None)
    return render_template('index.html', roots=roots)

@app.route('/wiki/<int:page_id>')
def view_page(page_id):
    page = get_page(page_id)
    if not page:
        return "문서를 찾을 수 없습니다.", 404
    children = get_children(page_id)
    return render_template('view.html', page=page, children=children)

@app.route('/new/<parent_id>', methods=['GET','POST'])
def new_page(parent_id):
    if parent_id == "None":
        parent_id = None
    else:
        parent_id = int(parent_id)

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO pages (parent_id, title, content) VALUES (?,?,?)",
                        (parent_id, title, content))
            conn.commit()
            new_id = cur.lastrowid
        return redirect(url_for('view_page', page_id=new_id))
    return render_template('edit.html', page=None, parent_id=parent_id)

@app.route('/edit/<int:page_id>', methods=['GET','POST'])
def edit_page(page_id):
    page = get_page(page_id)
    if not page:
        return "문서를 찾을 수 없습니다.", 404

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE pages SET title=?, content=? WHERE id=?", (title, content, page_id))
            conn.commit()
        return redirect(url_for('view_page', page_id=page_id))

    return render_template('edit.html', page=page, parent_id=page[1])

def delete_recursive(page_id):
    children = get_children(page_id)
    for child in children:
        delete_recursive(child[0])
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM pages WHERE id=?", (page_id,))
        conn.commit()

@app.route('/delete/<int:page_id>')
def delete_page(page_id):
    page = get_page(page_id)
    if not page:
        return "문서를 찾을 수 없습니다.", 404
    delete_recursive(page_id)
    if page[1] is None:
        return redirect(url_for('index'))
    else:
        return redirect(url_for('view_page', page_id=page[1]))

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                FOREIGN KEY(parent_id) REFERENCES pages(id)
            );
            """)
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
