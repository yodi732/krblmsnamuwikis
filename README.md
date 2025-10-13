# 별내위키 - 프로덕션 SMTP 포함 버전

## 환경변수
필수:
- SECRET_KEY
- DATABASE_URL (Render/Heroku Postgres URL; `postgres://`는 자동으로 `postgresql+psycopg://`로 보정)
- APP_BASE_URL (예: https://krblmsnamuwikis.onrender.com)
- ALLOWED_EMAIL_DOMAIN=bl-m.kr

SMTP (실제 발송):
- SMTP_HOST
- SMTP_PORT
- SMTP_USERNAME
- SMTP_PASSWORD
- SMTP_FROM (예: "별내위키 <no-reply@bl-m.kr>")
- SMTP_USE_TLS=true (또는 SMTP_USE_SSL=true 중 하나)

선택:
- SMTP_REPLY_TO
- SMTP_TIMEOUT=15, SMTP_MAX_RETRIES=3, SMTP_RETRY_BACKOFF=2

## 실행
pip install -r requirements.txt
export FLASK_ENV=production
gunicorn app:app --bind 0.0.0.0:8000
