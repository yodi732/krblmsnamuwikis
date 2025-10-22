# 별내위키 (Render 배포용)

## 실행
- Build: `pip install -r requirements.txt`
- Start: `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`

## 환경 변수
- `DATABASE_URL`: Postgres URL (postgres://... 지원, 자동 변환)
- `SECRET_KEY`: 세션 키

## 주요 정책
- 약관/개인정보처리방침은 /legal/* 라우트로 제공되며 위키 문서가 아님(수정/삭제 불가)
- 문서 생성/편집/삭제/로그 보기: 로그인 필요
- 하위문서 한 단계만 허용
