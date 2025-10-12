# 별내위키 (Flask) – Render 배포본
- psycopg3 드라이버 사용 (psycopg[binary])
- 기존 DB 자동 스키마 보정(created_at/parent_id)
- 홈/생성 페이지 동기화된 리스트, 삭제 버튼 우측 정렬
- 상단 네비게이션 버튼 우측 정렬

## 환경 변수
- DATABASE_URL (예: postgres://... → 코드가 postgresql+psycopg:// 로 변환)
- SECRET_KEY
- LOG_ANONYMIZE_IP (기본 true)

## 실행
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg://USER:PASS@HOST:PORT/DB"
export SECRET_KEY="something-secret"
gunicorn app:app
