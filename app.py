
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from pathlib import Path
import sqlite3, os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# --- DB hardening / auto-init ---
HERE = Path(__file__).parent
INSTANCE_DIR = HERE / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
DB_PATH = INSTANCE_DIR / "database.db"
SCHEMA_PATH = HERE / "schema.sql"

def get_conn():
    # Single responsibility: return a new connection. No recursion.
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def ensure_schema():
    if SCHEMA_PATH.exists():
        with sqlite3.connect(str(DB_PATH)) as conn:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            conn.commit()

# Apply schema once on import (safe if repeated)
ensure_schema()

# --- Routes ---
@app.get("/health")
def health():
    try:
        with get_conn() as con:
            con.execute("SELECT 1")
        return {"ok": True}, 200
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

@app.get("/")
def index():
    q = request.args.get("q", "").strip()
    with get_conn() as con:
        if q:
            rows = con.execute(
                "SELECT id, title, created_at FROM sections WHERE title LIKE ? OR content LIKE ? ORDER BY created_at DESC",
                (f"%{q}%", f"%{q}%"),
            ).fetchall()
        else:
            rows = con.execute("SELECT id, title, created_at FROM sections ORDER BY created_at DESC").fetchall()
    return render_template("index.html", sections=rows, q=q)

@app.route("/sections/add", methods=["GET", "POST"])
def add_section():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if not title:
            flash("제목은 비워둘 수 없습니다.", "error")
            return redirect(url_for("add_section"))
        with get_conn() as con:
            con.execute("INSERT INTO sections (title, content) VALUES (?, ?)", (title, content))
            con.commit()
        flash("새 글이 생성되었습니다.", "success")
        return redirect(url_for("index"))
    return render_template("add_section.html")

@app.get("/sections/<int:section_id>")
def view_section(section_id):
    with get_conn() as con:
        row = con.execute("SELECT * FROM sections WHERE id = ?", (section_id,)).fetchone()
    if not row:
        abort(404)
    return render_template("section.html", section=row)

@app.route("/sections/<int:section_id>/edit", methods=["GET", "POST"])
def edit_section(section_id):
    with get_conn() as con:
        row = con.execute("SELECT * FROM sections WHERE id = ?", (section_id,)).fetchone()
    if not row:
        abort(404)

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if not title:
            flash("제목은 비워둘 수 없습니다.", "error")
            return redirect(url_for("edit_section", section_id=section_id))
        with get_conn() as con:
            con.execute("UPDATE sections SET title = ?, content = ? WHERE id = ?", (title, content, section_id))
            con.commit()
        flash("수정되었습니다.", "success")
        return redirect(url_for("view_section", section_id=section_id))

    return render_template("edit_section.html", section=row)

@app.post("/sections/<int:section_id>/delete")
def delete_section(section_id):
    with get_conn() as con:
        con.execute("DELETE FROM sections WHERE id = ?", (section_id,))
        con.commit()
    flash("삭제했습니다.", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    # For local dev only. Render will use gunicorn.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
