# byeollae-wiki DB 핫픽스 (v2)

## 하는 일
1) `document.title`에 UNIQUE 인덱스 생성 — 앱 시드 쿼리 `ON CONFLICT (title) DO NOTHING` 정상화.
2) 사용자 테이블 컬럼명이 앱 코드(`pw_hash`)와 다를 경우, `password_hash`를 `pw_hash`로 안전히 변경.
3) `user.email`에 UNIQUE 인덱스 추가 — 중복 가입 방지.

## 실행 방법
### Render 대시보드에서
PostgreSQL 콘솔(psql)에서 `db_hotfix.sql` 내용을 그대로 붙여넣고 실행.

### CLI
psql "$DATABASE_URL" -f db_hotfix.sql

## 적용 후
서비스를 재시작(리디플로이)하세요.
