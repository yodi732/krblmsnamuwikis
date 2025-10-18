
# Flask + Render + PostgreSQL (SSL Fix)

## ✅ 배포 전 해야 할 것
1. Render 환경변수:
   - DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require
   - RUN_DB_INIT=1 (처음만 필요)
2. Start Command:
   ```
   gunicorn app:app --bind 0.0.0.0:$PORT
   ```
3. 배포 후 테스트:
   - `/` : HTML 페이지 정상 출력
   - `/add/test` : DB 연결 및 INSERT 확인
   - `/healthz` : JSON 응답 {"status":"ok"}

## ⚙️ 주요 수정점
- SSL 연결(`sslmode=require`) 강제
- pool_pre_ping, recycle 등 안정화 옵션 추가
- DB init 자동 재시도 로직 포함
- 연결 실패 시에도 앱이 500으로 죽지 않음
