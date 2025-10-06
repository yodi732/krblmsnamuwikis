from flask import Flask, render_template, request, redirect, url_for, flash
from markupsafe import Markup
import sqlite3, os, re, markdown, urllib.parse

DB_PATH = os.path.join(os.path.dirname(__file__), 'wiki.db')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

def get_conn():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS pages (
        title TEXT PRIMARY KEY,
        content TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

init_db()

INTERNAL_LINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')

def convert_internal_links(text):
    def repl(m):
        target = m.group(1).strip()
        label = (m.group(2) or m.group(1)).strip()
        url = '/wiki/' + urllib.parse.quote(target, safe='')
        return f'[{label}]({url})'
    return INTERNAL_LINK_RE.sub(repl, text)

def render_content(raw):
    if not raw:
        return ''
    md = convert_internal_links(raw)
    html = markdown.markdown(md, extensions=['fenced_code','tables'])
    return Markup(html)

@app.route('/')
def index():
    conn = get_conn()
    rows = conn.execute("SELECT title FROM pages ORDER BY title COLLATE NOCASE").fetchall()
    conn.close()
    pages = [r['title'] for r in rows]
    return render_template('index.html', pages=pages)

@app.route('/wiki/<path:title>')
def view_page(title):
    conn = get_conn()
    row = conn.execute("SELECT content, updated_at FROM pages WHERE title=?", (title,)).fetchone()
    conn.close()
    if not row:
        return render_template('notfound.html', title=title)
    content = render_content(row['content'])
    return render_template('page.html', title=title, content=content, updated_at=row['updated_at'])

@app.route('/edit/<path:title>', methods=['GET','POST'])
def edit_page(title):
    conn = get_conn()
    if request.method == 'POST':
        content = request.form.get('content','')
        conn.execute("REPLACE INTO pages (title, content, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                     (title, content))
        conn.commit()
        conn.close()
        flash('Saved successfully.', 'success')
        return redirect(url_for('view_page', title=title))
    row = conn.execute("SELECT content FROM pages WHERE title=?", (title,)).fetchone()
    conn.close()
    content = row['content'] if row else ''
    return render_template('edit.html', title=title, content=content)

@app.route('/delete/<path:title>', methods=['GET','POST'])
def delete_page(title):
    if request.method == 'POST':
        conn = get_conn()
        conn.execute("DELETE FROM pages WHERE title=?", (title,))
        conn.commit()
        conn.close()
        flash(f'Page "{title}" deleted.', 'info')
        return redirect(url_for('index'))
    return render_template('delete_confirm.html', title=title)

@app.route('/list')
def list_pages():
    conn = get_conn()
    rows = conn.execute("SELECT title, updated_at FROM pages ORDER BY title COLLATE NOCASE").fetchall()
    conn.close()
    return render_template('list.html', pages=rows)

@app.route('/recent')
def recent():
    conn = get_conn()
    rows = conn.execute("SELECT title, updated_at FROM pages ORDER BY updated_at DESC LIMIT 20").fetchall()
    conn.close()
    return render_template('recent.html', pages=rows)

@app.route('/search')
def search():
    q = request.args.get('q','').strip()
    results = []
    if q:
        conn = get_conn()
        rows = conn.execute("SELECT title, updated_at FROM pages WHERE lower(title) LIKE ? ORDER BY title COLLATE NOCASE",
                           (f'%{q.lower()}%',)).fetchall()
        conn.close()
        results = rows
    return render_template('search.html', q=q, results=results)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '10000'))
    app.run(host='0.0.0.0', port=port)
