# NamuWiki-lite (Render + Supabase final)

## 환경변수 (Render → Environment)

- `DATABASE_URL` (예시)
  `postgresql+psycopg://postgres:<비밀번호>@db.<프로젝트-ref>.supabase.co:6543/postgres?sslmode=require&connect_timeout=10`
- `SECRET_KEY` : 임의의 긴 랜덤 문자열

> 참고: URL이 `postgresql://`로 시작한다면 앱이 자동으로 `postgresql+psycopg://`로 변환합니다.

## Start Command (Render)
```
gunicorn app:app --bind 0.0.0.0:$PORT
```

## 안정화 포인트
- Flask 3 호환 (before_first_request 미사용)
- DB 초기화/핑 실패 시에도 앱은 구동 (읽기/쓰기 버튼은 안내 메시지)
- 풀 pre_ping, 빠른 connect_timeout
- `/healthz` 헬스엔드포인트 제공
