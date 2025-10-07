
# KR BLMS NamuWiki — Render-ready

## Deploy
1. Push this repo to GitHub.
2. On Render: Web Service
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `bash -c "python init_db.py && gunicorn app:app --bind 0.0.0.0:$PORT"`
3. First boot will create `instance/database.db` from `schema.sql`.
