# Flask HTML Starter for Render

- Root (`/`) renders an HTML page.
- Health check JSON is at `/healthz`.
- Add a demo DB row with `/add/<name>`.

## Render settings
- Start Command:
  `gunicorn app:app --bind 0.0.0.0:$PORT`
- Environment:
  `DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/DB?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt`
- Optional:
  `RUN_DB_INIT=1`