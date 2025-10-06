from flask import Flask, render_template, request, redirect, url_for, flash
from markupsafe import Markup
import sqlite3, os, re, markdown, urllib.parse

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "wiki.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

def get_conn():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_id INTEGER,
        title TEXT UNIQUE,
        content TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(section_id) REFERENCES sections(id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        object_type TEXT,
        object_id INTEGER,
        object_title TEXT,
        details TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

init_db()

# Internal link pattern [[Page]] or [[Page|Label]]
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
        return Markup('')
    md = convert_internal_links(raw)
    html = markdown.markdown(md, extensions=['fenced_code', 'tables'])
    return Markup(html)

def log_action(action, object_type, object_id, object_title, details=''):
    conn = get_conn()
    conn.execute("""INSERT INTO logs (action, object_type, object_id, object_title, details)
                    VALUES (?, ?, ?, ?, ?)""", (action, object_type, object_id, object_title, details))
    conn.commit()
    conn.close()

@app.context_processor
def inject_sections():
    conn = get_conn()
    rows = conn.execute("SELECT id, title FROM sections ORDER BY title COLLATE NOCASE").fetchall()
    conn.close()
    return dict(all_sections=rows)

@app.route('/')
def index():
    # Show sections and link to create section
    conn = get_conn()
    rows = conn.execute("SELECT id, title, created_at, (SELECT COUNT(*) FROM pages WHERE section_id=sections.id) as page_count FROM sections ORDER BY title COLLATE NOCASE").fetchall()
    conn.close()
    return render_template('index.html', sections=rows)

@app.route('/section/<int:section_id>')
def view_section(section_id):
    conn = get_conn()
    section = conn.execute("SELECT id, title FROM sections WHERE id=?", (section_id,)).fetchone()
    if not section:
        conn.close()
        flash('Section not found.', 'error')
        return redirect(url_for('index'))
    pages = conn.execute("SELECT id, title, updated_at FROM pages WHERE section_id=? ORDER BY title COLLATE NOCASE", (section_id,)).fetchall()
    conn.close()
    return render_template('section.html', section=section, pages=pages)

@app.route('/add_section', methods=['GET','POST'])
def add_section():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        if not title:
            flash('Section title required.', 'error')
            return redirect(url_for('index'))
        conn = get_conn()
        try:
            cur = conn.execute("INSERT INTO sections (title) VALUES (?)", (title,))
            conn.commit()
            section_id = cur.lastrowid
            log_action('add', 'section', section_id, title)
            flash('Section created.', 'success')
        except sqlite3.IntegrityError:
            flash('Section title already exists.', 'error')
        conn.close()
        return redirect(url_for('index'))
    return render_template('add_section.html')

@app.route('/delete_section/<int:section_id>', methods=['GET','POST'])
def delete_section(section_id):
    conn = get_conn()
    section = conn.execute("SELECT id, title FROM sections WHERE id=?", (section_id,)).fetchone()
    if not section:
        conn.close()
        flash('Section not found.', 'error')
        return redirect(url_for('index'))
    if request.method == 'POST':
        # delete pages in section and log each deletion
        pages = conn.execute("SELECT id, title FROM pages WHERE section_id=?", (section_id,)).fetchall()
        for p in pages:
            conn.execute("DELETE FROM pages WHERE id=?", (p['id'],))
            log_action('delete', 'page', p['id'], p['title'], f'deleted as part of section delete {section["title"]}')
        conn.execute("DELETE FROM sections WHERE id=?", (section_id,))
        conn.commit()
        log_action('delete', 'section', section_id, section['title'], 'section and its pages deleted')
        conn.close()
        flash('Section and its pages deleted.', 'info')
        return redirect(url_for('index'))
    conn.close()
    return render_template('delete_section_confirm.html', section=section)

@app.route('/add_page/<int:section_id>', methods=['GET','POST'])
def add_page(section_id):
    conn = get_conn()
    section = conn.execute("SELECT id, title FROM sections WHERE id=?", (section_id,)).fetchone()
    if not section:
        conn.close()
        flash('Section not found.', 'error')
        return redirect(url_for('index'))
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        content = request.form.get('content','')
        if not title:
            flash('Page title required.', 'error')
            conn.close()
            return redirect(url_for('view_section', section_id=section_id))
        try:
            cur = conn.execute("INSERT INTO pages (section_id, title, content) VALUES (?, ?, ?)", (section_id, title, content))
            conn.commit()
            page_id = cur.lastrowid
            log_action('add', 'page', page_id, title, f'created in section {section["title"]}')
            flash('Page created.', 'success')
            conn.close()
            return redirect(url_for('view_page', page_id=page_id))
        except sqlite3.IntegrityError:
            flash('A page with that title already exists.', 'error')
            conn.close()
            return redirect(url_for('view_section', section_id=section_id))
    conn.close()
    return render_template('add_page.html', section=section)

@app.route('/page/<int:page_id>')
def view_page(page_id):
    conn = get_conn()
    row = conn.execute("SELECT p.id, p.title, p.content, p.updated_at, s.id as section_id, s.title as section_title FROM pages p LEFT JOIN sections s ON p.section_id=s.id WHERE p.id=?", (page_id,)).fetchone()
    conn.close()
    if not row:
        flash('Page not found.', 'error')
        return redirect(url_for('index'))
    content = render_content(row['content'])
    return render_template('page.html', page=row, content=content)

@app.route('/wiki/<path:title>')
def view_page_by_title(title):
    # title is URL-decoded by Flask
    conn = get_conn()
    row = conn.execute("SELECT id FROM pages WHERE title=?", (title,)).fetchone()
    conn.close()
    if not row:
        # offer creation: user can choose section to create under
        conn2 = get_conn()
        sections = conn2.execute("SELECT id, title FROM sections ORDER BY title COLLATE NOCASE").fetchall()
        conn2.close()
        return render_template('notfound_create.html', title=title, sections=sections)
    return redirect(url_for('view_page', page_id=row['id']))

@app.route('/edit_page/<int:page_id>', methods=['GET','POST'])
def edit_page(page_id):
    conn = get_conn()
    row = conn.execute("SELECT id, title, content, section_id FROM pages WHERE id=?", (page_id,)).fetchone()
    if not row:
        conn.close()
        flash('Page not found.', 'error')
        return redirect(url_for('index'))
    if request.method == 'POST':
        content = request.form.get('content','')
        conn.execute("UPDATE pages SET content=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (content, page_id))
        conn.commit()
        log_action('edit', 'page', page_id, row['title'], 'content updated')
        conn.close()
        flash('Page updated.', 'success')
        return redirect(url_for('view_page', page_id=page_id))
    conn.close()
    return render_template('edit_page.html', page=row)

@app.route('/delete_page/<int:page_id>', methods=['GET','POST'])
def delete_page(page_id):
    conn = get_conn()
    row = conn.execute("SELECT id, title, section_id FROM pages WHERE id=?", (page_id,)).fetchone()
    if not row:
        conn.close()
        flash('Page not found.', 'error')
        return redirect(url_for('index'))
    if request.method == 'POST':
        conn.execute("DELETE FROM pages WHERE id=?", (page_id,))
        conn.commit()
        log_action('delete', 'page', page_id, row['title'], 'deleted by user')
        conn.close()
        flash('Page deleted.', 'info')
        return redirect(url_for('view_section', section_id=row['section_id']) if row['section_id'] else url_for('index'))
    conn.close()
    return render_template('delete_page_confirm.html', page=row)

@app.route('/logs')
def logs():
    conn = get_conn()
    rows = conn.execute("SELECT id, action, object_type, object_title, details, timestamp FROM logs ORDER BY timestamp DESC LIMIT 50").fetchall()
    conn.close()
    return render_template('logs.html', logs=rows)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '10000'))
    app.run(host='0.0.0.0', port=port)
