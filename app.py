from flask import Flask, render_template, request, redirect, url_for, flash, abort
from pathlib import Path
import sqlite3, os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this")

# ---- DB: path & auto schema ----
HERE = Path(__file__).parent
INSTANCE = HERE / "instance"
INSTANCE.mkdir(exist_ok=True)
DB_PATH = INSTANCE / "database.db"
SCHEMA_PATH = HERE / "schema.sql"

def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def ensure_schema():
    if SCHEMA_PATH.exists():
        with sqlite3.connect(str(DB_PATH)) as con:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                con.executescript(f.read())
            con.commit()

# apply on import (idempotent)
ensure_schema()

# ---- helpers ----
def is_root(page_id):
    if page_id is None:
        return True
    with get_conn() as con:
        row = con.execute("SELECT parent_id FROM pages WHERE id=?", (page_id,)).fetchone()
        if not row:
            return True
        return row["parent_id"] is None

def all_pages():
    with get_conn() as con:
        return con.execute(
            """
            SELECT id, title, parent_id, created_at, updated_at
            FROM pages
            ORDER BY parent_id IS NOT NULL, title COLLATE NOCASE
            """
        ).fetchall()

def tree_by_parent(rows):
    t = {}
    for r in rows:
        t.setdefault(r["parent_id"], []).append(r)
    return t

def log_action(con, page_id, author, action, summary):
    con.execute(
        "INSERT INTO page_logs(page_id, author, action, summary) VALUES (?,?,?,?)",
        (page_id, author or "anonymous", action, summary or ""),
    )

# ---- routes ----
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
    pages = all_pages()
    tree = tree_by_parent(pages)
    with get_conn() as con:
        roots = con.execute(
            "SELECT id, title, created_at, updated_at FROM pages WHERE parent_id IS NULL ORDER BY title COLLATE NOCASE"
        ).fetchall()
    return render_template("index.html", roots=roots, tree=tree)

@app.route("/pages/new", methods=["GET", "POST"])
def new_page():
    default_parent = request.args.get("parent", "").strip()
    with get_conn() as con:
        allp = con.execute("SELECT id, title FROM pages ORDER BY title COLLATE NOCASE").fetchall()
    tree = tree_by_parent(all_pages())
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        parent_id = request.form.get("parent_id") or None
        # depth limit: only root -> child allowed
        try:
            blocked = parent_id not in (None, "", "None") and (not is_root(parent_id))
        except Exception:
            blocked = False
        if blocked:
            flash("하위 문서의 하위로 이동할 수 없습니다.", "error")
            return redirect(url_for("edit_page", page_id=page_id))
        # depth limit: only root -> child allowed
        if parent_id not in (None, "", "None") and not is_root(int(parent_id)):
            flash("하위 문서의 하위 문서는 만들 수 없습니다.", "error")
            return redirect(url_for("new_page"))
        author = (request.form.get("author") or "anonymous").strip()
        summary = (request.form.get("summary") or "").strip()
        if not title:
            flash("제목은 비워둘 수 없습니다.", "error")
            return redirect(url_for("new_page"))
        with get_conn() as con:
            cur = con.execute(
                "INSERT INTO pages(title, content, parent_id) VALUES (?,?,?)",
                (title, content, parent_id if parent_id not in (None, "", "None") else None),
            )
            pid = cur.lastrowid
            log_action(con, pid, author, "create", summary or f"페이지 생성: {title}")
            con.commit()
        flash("페이지가 생성되었습니다.", "success")
        return redirect(url_for("view_page", page_id=pid))
    return render_template("new_page.html", all_pages=allp, default_parent=default_parent, tree=tree)

@app.get("/p/<int:page_id>")
def view_page(page_id):
    with get_conn() as con:
        page = con.execute("SELECT * FROM pages WHERE id=?", (page_id,)).fetchone()
        if not page:
            abort(404)
        kids = con.execute("SELECT id, title FROM pages WHERE parent_id=? ORDER BY title COLLATE NOCASE", (page_id,)).fetchall()
    tree = tree_by_parent(all_pages())
    return render_template("page.html", page=page, children=kids, tree=tree)

@app.route("/p/<int:page_id>/edit", methods=["GET", "POST"])
def edit_page(page_id):
    with get_conn() as con:
        page = con.execute("SELECT * FROM pages WHERE id=?", (page_id,)).fetchone()
        allp = con.execute("SELECT id, title FROM pages WHERE parent_id IS NULL AND id != ? ORDER BY title COLLATE NOCASE", (page_id,)).fetchall()
    tree = tree_by_parent(all_pages())
    if not page:
        abort(404)
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        parent_id = request.form.get("parent_id") or None
        # depth limit: only root -> child allowed
        try:
            blocked = parent_id not in (None, "", "None") and (not is_root(parent_id))
        except Exception:
            blocked = False
        if blocked:
            flash("하위 문서의 하위로 이동할 수 없습니다.", "error")
            return redirect(url_for("edit_page", page_id=page_id))
        # depth limit: only root -> child allowed
        if parent_id not in (None, "", "None") and not is_root(int(parent_id)):
            flash("하위 문서의 하위 문서는 만들 수 없습니다.", "error")
            return redirect(url_for("new_page"))
        author = (request.form.get("author") or "anonymous").strip()
        summary = (request.form.get("summary") or "").strip()
        if not title:
            flash("제목은 비워둘 수 없습니다.", "error")
            return redirect(url_for("edit_page", page_id=page_id))
        with get_conn() as con:
            con.execute(
                "UPDATE pages SET title=?, content=?, parent_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (title, content, parent_id if parent_id not in (None, "", "None") else None, page_id),
            )
            log_action(con, page_id, author, "edit", summary or f"페이지 수정: {title}")
            con.commit()
        flash("수정되었습니다.", "success")
        return redirect(url_for("view_page", page_id=page_id))
    return render_template("edit_page.html", page=page, all_pages=allp, tree=tree)

@app.post("/p/<int:page_id>/delete")
def delete_page(page_id):
    author = (request.form.get("author") or "anonymous").strip()
    summary = (request.form.get("summary") or "삭제").strip()
    with get_conn() as con:
        ex = con.execute("SELECT 1 FROM pages WHERE id=?", (page_id,)).fetchone()
        if not ex:
            abort(404)
        cnt = con.execute("SELECT COUNT(*) AS c FROM pages WHERE parent_id=?", (page_id,)).fetchone()["c"]
        if cnt > 0:
            flash("하위 문서가 있어 삭제할 수 없습니다. 먼저 하위 문서를 삭제하세요.", "error")
            return redirect(url_for("view_page", page_id=page_id))
        log_action(con, page_id, author, "delete", summary)
        con.execute("DELETE FROM pages WHERE id=?", (page_id,))
        con.commit()
    flash("삭제했습니다.", "success")
    return redirect(url_for("index"))

@app.get("/p/<int:page_id>/logs")
def page_logs(page_id):
    with get_conn() as con:
        page = con.execute("SELECT id, title FROM pages WHERE id=?", (page_id,)).fetchone()
        if not page:
            abort(404)
        logs = con.execute(
            "SELECT id, author, action, summary, created_at FROM page_logs WHERE page_id=? ORDER BY id DESC",
            (page_id,)
        ).fetchall()
    tree = tree_by_parent(all_pages())
    return render_template("logs.html", page=page, logs=logs, tree=tree)

# jinja helper
@app.context_processor
def _helpers():
    def render_toc(tree, parent_id=None, current_id=None, depth=0, max_depth=6):
        items = tree.get(parent_id, [])
        if not items or depth > max_depth:
            return ""
        html = [f"<ul class='toc depth-{depth}'>"]
        for p in items:
            cls = "current" if p["id"] == current_id else ""
            html.append(f"<li class='{cls}'><a href='{url_for('view_page', page_id=p['id'])}'>{p['title']}</a>")
            html.append(render_toc(tree, p["id"], current_id, depth+1, max_depth))
            html.append("</li>")
        html.append("</ul>")
        return "".join(html)
    return dict(render_toc=render_toc)

@app.get("/logs")
def logs_all():
    with get_conn() as con:
        rows = con.execute(
            "SELECT l.id, l.page_id, p.title as page_title, l.author, l.action, l.summary, l.created_at "
            "FROM page_logs l LEFT JOIN pages p ON p.id=l.page_id ORDER BY l.id DESC LIMIT 500"
        ).fetchall()
    tree = tree_by_parent(all_pages())
    return render_template("logs_all.html", logs=rows, tree=tree)
