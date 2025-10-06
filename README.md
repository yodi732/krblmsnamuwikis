# Simple Tree-style Wiki (Render-ready)

This is a minimal tree-structured wiki inspired by Namuwiki. Features:
- Sections (목차) and Pages (하위문서)
- Create / Edit / Delete sections and pages
- Internal links using [[Page Title]]
- Logs of add/edit/delete actions (view at /logs)
- SQLite DB stored as wiki.db (preserved between deploys unless you remove it)
- No search (requested)
- Render-ready (render.yaml included), start command uses gunicorn

To deploy:
1. Upload repo to GitHub
2. Connect repository to Render (it will use render.yaml)
3. Build will run `pip install -r requirements.txt` and start gunicorn
