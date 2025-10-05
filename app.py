from flask import Flask, render_template, request, redirect, url_for, flash, Markup
import sqlite3, os, re, datetime, html
import markdown as md
from urllib.parse import quote, unquote

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "wiki.db")

app = Flask(__name__)
app.secret_key = "change-this-to-a-secret"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # safe, non-destructive initialization
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS pages (
            title TEXT PRIMARY KEY,
            content TEXT DEFAULT '',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_pages_updated ON pages(updated_at);
        """)
        conn.commit()

# ensure DB exists / schema present on startup
init_db()

# Heading regex for ==Heading== style (2-6 equals)
heading_re = re.compile(r'^(={2,6})\s*(.+?)\s*\1\s*$', re.MULTILINE)
wikilink_re = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')  # [[Target|Label]] or [[Target]]

def slug_for_anchor(text):
    s = re.sub(r'[^0-9a-zA-Z가-힣 _\-]', '', text)
    s = s.replace(' ', '-').lower()
    return s

def convert_headings_to_md(text):
    # Convert Namu-style == Heading == into markdown headings (## ...)
    def repl(m):
        level = len(m.group(1))  # number of '='
        title = m.group(2).strip()
        md_level = min(level, 6)  # map to up to ######
        return '\n' + ('#' * md_level) + ' ' + title + '\n'
    return heading_re.sub(repl, text)

def convert_wikilinks_to_markdown(text):
    # convert [[Target|Label]] to markdown [Label](/w/Target)
    def repl(m):
        target = m.group(1).strip()
        label = m.group(2).strip() if m.group(2) else target
        url = '/w/' + quote(target, safe='')
        # escape label for markdown link text
        label_escaped = label.replace('[', '\\[').replace(']', '\\]')
        return f'[{label_escaped}]({url})'
    return wikilink_re.sub(repl, text)

def render_content(raw):
    raw = raw or ''
    # first convert wikilinks then headings to keep anchors consistent
    processed = convert_wikilinks_to_markdown(raw)
    processed = convert_headings_to_md(processed)
    # render markdown to HTML, enable sane features
    html_body = md.markdown(processed, extensions=['extra','sane_lists','toc'])
    # build TOC from headings in processed text
    toc = []
    for i, line in enumerate(processed.splitlines()):
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            anchor = slug_for_anchor(text) + f'-{i}'
            toc.append({'level': level, 'text': text, 'anchor': anchor})
            # inject id into html headings (first matching occurrence)
            pattern = re.compile(rf'(<h{level}[^>]*>)\s*({re.escape(text)})', re.IGNORECASE)
            html_body, n = pattern.subn(rf'\1<a id="{anchor}"></a>\2', html_body, count=1)
    return html_body, toc

@app.route('/')
def index():
    q = request.args.get('q','').strip()
    conn = get_conn()
    cur = conn.cursor()
    if q:
        like = f'%{q}%'
        cur.execute("SELECT title, updated_at FROM pages WHERE title LIKE ? OR content LIKE ? ORDER BY updated_at DESC LIMIT 200", (like, like))
        results = cur.fetchall()
        conn.close()
        return render_template('index.html', results=results, query=q)
    else:
        cur.execute("SELECT title, updated_at FROM pages ORDER BY updated_at DESC LIMIT 50")
        recent = cur.fetchall()
        conn.close()
        return render_template('index.html', recent=recent, query='')

@app.route('/w/<path:title>')
def view(title):
    title = unquote(title).strip()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT title, content FROM pages WHERE title=?", (title,))
    row = cur.fetchone()
    conn.close()
    if not row:
        # render missing page view
        return render_template('view.html', title=title, content=None, toc=None)
    html_body, toc = render_content(row['content'])
    return render_template('view.html', title=row['title'], content=Markup(html_body), toc=toc)

@app.route('/edit/<path:title>', methods=['GET','POST'])
def edit(title):
    title = unquote(title).strip()
    conn = get_conn()
    cur = conn.cursor()
    if request.method == 'POST':
        new_title = request.form.get('title','').strip()
        content = request.form.get('content','')
        if not new_title:
            flash("제목을 입력하세요.", "error")
            return redirect(url_for('edit', title=title))
        # rename handling: if new_title != title and exists -> error
        if new_title != title:
            cur.execute("SELECT title FROM pages WHERE title=?", (new_title,))
            if cur.fetchone():
                flash("이미 존재하는 문서 제목입니다.", "error")
                conn.close()
                return redirect(url_for('edit', title=title))
            # safe rename: insert new then delete old
            cur.execute("INSERT INTO pages (title, content, updated_at) VALUES (?,?,?)", (new_title, content, datetime.datetime.utcnow().isoformat()))
            cur.execute("DELETE FROM pages WHERE title=?", (title,))
        else:
            cur.execute("INSERT OR REPLACE INTO pages (title, content, updated_at) VALUES (?,?,?)", (new_title, content, datetime.datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        flash("문서이 저장되었습니다.", "success")
        return redirect(url_for('view', title=quote(new_title, safe='')))
    else:
        cur.execute("SELECT title, content FROM pages WHERE title=?", (title,))
        row = cur.fetchone()
        conn.close()
        if row:
            return render_template('edit.html', title=row['title'], content=row['content'])
        else:
            # new page draft
            return render_template('edit.html', title=title, content='')

@app.route('/delete/<path:title>', methods=['POST'])
def delete(title):
    title = unquote(title).strip()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM pages WHERE title=?", (title,))
    conn.commit()
    conn.close()
    flash("문서를 삭제했습니다.", "info")
    return redirect(url_for('index'))

# simple redirect from bare /view to /w/
@app.route('/view/<path:title>')
def view_compat(title):
    return redirect(url_for('view', title=quote(title, safe='')))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
