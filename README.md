# 별내위키
- Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`
- Env:
  - DATABASE_URL (postgresql://...)
  - SECRET_KEY
앱 부팅 시 필요한 컬럼을 자동으로 보정하고 시스템 문서를 채웁니다.
