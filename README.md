# 별내위키 (Flask)

Render 외부 Postgres + Flask 배포용 최종본.

## 환경 변수
- `DATABASE_URL` : Render 외부 PostgreSQL 주소 (필수)
- `SECRET_KEY` : Flask 시크릿 키 (필수)
- `LOG_ANONYMIZE_IP` : IP 익명화 적용 여부 (기본 true)

## 실행
```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql://..."
export SECRET_KEY="something-secret"
gunicorn app:app
```

## 기능
- 상위/하위 문서 생성 (하위의 하위 금지)
- 홈 및 생성 페이지에서 동일한 목록 뷰 사용 (동기화)
- 문서 삭제(홈/생성 화면 모두에서), 부모 삭제 시 자식도 함께 삭제
- 작업 로그 확인(시간/동작/문서/익명화 IP)


드라이버: psycopg3 (psycopg[binary]) 사용. DATABASE_URL은 postgresql(+psycopg)로 정규화됩니다.
