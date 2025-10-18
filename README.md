# Render Flask + Postgres (TLS verified) Quickstart

이 템플릿은 Render의 Postgres **pooler**에 TLS 검증을 제대로 걸어
`SSL connection has been closed unexpectedly` 오류를 방지하도록 구성되어 있습니다.

## 1) 환경변수 설정

Render 대시보드 → **Environment**

`DATABASE_URL` 값을 다음과 같이 설정하세요 (예시 값은 본인 DB 정보로 자동 채워짐):

```
postgresql+psycopg://<USER>:<PASS>@<HOST>:5432/<DBNAME>?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt
```

- 포인트:
  - `postgresql+psycopg` (psycopg3 드라이버)
  - `sslmode=verify-full`
  - `sslrootcert=/etc/ssl/certs/ca-certificates.crt`

> 코드에서도 같은 설정을 **강제**하므로, `DATABASE_URL`에 위 파라미터를 넣지 않아도 동작하지만
> 환경변수에도 동일하게 맞춰두면 가장 안전합니다.

## 2) Start Command (Render → Settings → Start Command)

가장 단순하게 아래처럼 두세요:

```
gunicorn app:app --bind 0.0.0.0:$PORT
```

이전처럼 heredoc/여러 줄 쉘을 섞으면 Render의 wrapping과 충돌해
`syntax error near unexpected token '('` 등의 파싱 에러가 날 수 있습니다.

## 3) 최초 테이블 생성

앱 부팅 시 `RUN_DB_INIT=1`(기본값) 상태라면 자동으로 `db.create_all()`이 한 번 실행됩니다.
이미 테이블이 있다면 아무 일도 일어나지 않습니다.
초기화 단계에서 문제가 있다면, 일단 **부팅은 계속** 하도록 처리되어 있습니다.

필요 시 Environment에 `RUN_DB_INIT=0`으로 꺼둘 수 있습니다.

## 4) 헬스 체크/기본 엔드포인트

- `/` : `{ "status": "ok", "db_uri": "postgresql+psycopg://..." }` 반환
- `/items` : 샘플 Item 목록

## 5) 로컬 실행 (선택)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg://USER:PASS@HOST:5432/DB?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt'
export RUN_DB_INIT=1
gunicorn app:app --bind 127.0.0.1:8000
```

---

### 문제 해결 Tips

- 여전히 TLS 에러가 난다면:
  1. `DATABASE_URL` 호스트가 Render **pooler** 주소인지 확인 (접미사 `-pooler`)
  2. `sslmode=verify-full`/`sslrootcert` 파라미터가 빠지지 않았는지 확인
  3. Render 환경에서 `/etc/ssl/certs/ca-certificates.crt` 경로가 존재하는지 확인 (기본 이미지엔 있음)

- 간헐적인 커넥션 끊김은 `pool_pre_ping=True`로 완화됩니다(기본 설정에 포함됨).
