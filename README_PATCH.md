# KRBLMS NamuWikis — SQLite DB Patch (Render Free Plan)

이 패치는 **디자인/기능은 전혀 바꾸지 않고**, Render 무료 플랜(SQLite)에서 반복되던
`user.password` / `document.created_by` **컬럼 누락 오류**만 해결합니다.

## 포함 파일
- `prestart.py` : 앱 시작 전에 SQLite 스키마를 자동으로 점검/보정합니다.
- `Procfile`    : gunicorn 실행 전에 `prestart.py`를 실행하도록 한 줄만 추가된 예시입니다.

## 적용 방법 (기존 코드 유지)
1. 이 zip을 기존 프로젝트 루트에 덮어씌웁니다. (기존 소스 변경 없음)
2. Render 환경변수에 다음이 있는지 확인합니다.
   ```
   DATABASE_URL=sqlite:///app.db
   ```
3. Procfile을 아래처럼 설정합니다.
   ```
   web: python prestart.py && gunicorn app:app --bind 0.0.0.0:$PORT
   ```
   - `app:app` 는 기존 WSGI 엔트리포인트 그대로 사용하세요. (예: `main:app` 이면 그걸로)
4. 재배포하면 로그에 아래 문구가 보입니다.
   - `[prestart] DB autofix completed`
   - `Your service is live 🎉`

## 동작 원리
- 테이블이 없으면 **생성**합니다. (user, document)
- 누락된 컬럼만 **안전하게 추가**합니다.
  - `user.password` (TEXT)
  - `document.created_by` (TEXT)
  - `document.updated_at` (DATETIME, 없을 때만)
- 이미 존재하는 경우 아무 것도 하지 않습니다. (idempotent)

## 주의
- 이 패치는 **SQLite 전용**입니다.
- PostgreSQL을 쓰는 경우에는 마이그레이션 툴(예: Alembic) 사용을 권장합니다.
