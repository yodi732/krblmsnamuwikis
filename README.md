# 별내위키 (Render 배포용)

## 핵심
- 디자인 원본 유지 (남색 상단바 + 흰 배경)
- 이용약관 / 개인정보처리방침: 보기 전용, 문서목록 비노출, 하단/회원가입에서만 접근
- DB 필드: `Document.content`만 사용 (기존 `body` 없음)
- 회원가입 시 필수 동의 체크만 (마케팅 동의 없음)

## 환경변수
- `DATABASE_URL` (Render Postgres) — 예: `postgresql://...`
  - 내부에서 `postgresql+psycopg://`로 자동 변환
- `SECRET_KEY` — 세션 키
- `PORT` — Render가 지정 (10000)

## 실행
```
gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
```

## 초기화/마이그레이션
- 앱 시작 시 `db.create_all()`로 테이블 생성
- 기존에 `document` 테이블이 있고 열 구성이 다르면 수동 마이그레이션 필요
  - (예) `ALTER TABLE document RENAME COLUMN body TO content;`
  - 또는 테이블을 백업 후 삭제/재생성