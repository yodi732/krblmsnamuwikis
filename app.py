from flask import Flask, render_template, request, redirect, url_for
import sqlite3, markdown

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect("wiki.db")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS pages (title TEXT PRIMARY KEY, content TEXT)""")
    conn.commit()
    conn.close()

init_db()

def get_page(title):
    conn = sqlite3.connect("wiki.db")
    cur = conn.cursor()
    cur.execute("SELECT content FROM pages WHERE title=?", (title,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

@app.route("/")
def index():
    conn = sqlite3.connect("wiki.db")
    cur = conn.cursor()
    cur.execute("SELECT title FROM pages")
    pages = [r[0] for r in cur.fetchall()]
    conn.close()
    return render_template("index.html", pages=pages)

@app.route("/wiki/<title>")
def view_page(title):
    content = get_page(title)
    if not content:
        return redirect(url_for("edit_page", title=title))
    html = markdown.markdown(content)
    return render_template("page.html", title=title, content=html)

@app.route("/edit/<title>", methods=["GET", "POST"])
def edit_page(title):
    if request.method == "POST":
        content = request.form["content"]
        conn = sqlite3.connect("wiki.db")
        cur = conn.cursor()
        cur.execute("REPLACE INTO pages (title, content) VALUES (?, ?)", (title, content))
        conn.commit()
        conn.close()
        return redirect(url_for("view_page", title=title))
    content = get_page(title) or ""
    return render_template("edit.html", title=title, content=content)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
