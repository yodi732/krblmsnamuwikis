
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3, os

app = Flask(__name__)

import os, sqlite3

# === Database initialization ===
def init_db():
    db_path = os.path.join(os.path.dirname(__file__), 'database.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

app.secret_key = 'secret'

def get_db():
    conn = sqlite3.connect('wiki.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db()
    sections = conn.execute("SELECT * FROM sections").fetchall()
    pages = conn.execute("SELECT * FROM pages").fetchall()
    return render_template('index.html', sections=sections, pages=pages)

@app.route('/section/<int:section_id>')
def section(section_id):
    conn = get_db()
    section = conn.execute("SELECT * FROM sections WHERE id=?", (section_id,)).fetchone()
    pages = conn.execute("SELECT * FROM pages WHERE section_id=?", (section_id,)).fetchall()
    return render_template('section.html', section=section, pages=pages)

@app.route('/page/<int:page_id>')
def page(page_id):
    conn = get_db()
    page = conn.execute("SELECT * FROM pages WHERE id=?", (page_id,)).fetchone()
    return render_template('page.html', page=page)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))


# --- Automatic database initialization (added automatically) ---
import sqlite3, logging
from pathlib import Path

def ensure_database():
    try:
        here = Path(__file__).parent
        instance_dir = here / 'instance'
        instance_dir.mkdir(exist_ok=True)
        db_path = instance_dir / 'database.db'
        if not db_path.exists():
            schema_path = here / 'schema.sql'
            if schema_path.exists():
                con = sqlite3.connect(str(db_path))
                with open(schema_path, 'r', encoding='utf-8') as f:
                    con.executescript(f.read())
                con.commit()
                con.close()
                logging.info(f"Database initialized automatically at {db_path}")
            else:
                logging.error("schema.sql not found; cannot initialize database automatically.")
        else:
            logging.info("Database already exists; skipping initialization.")
    except Exception as e:
        logging.exception(f"Error ensuring database: {e}")

# Automatically ensure DB when app starts
try:
    ensure_database()
except Exception as e:
    print("Automatic DB init failed:", e)
# --- End automatic initialization block ---