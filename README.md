
# krblmswiki (fixed)

Flask + SQLAlchemy 기반의 간단 위키. Render + Supabase에서의 연결 오류(IPv6 / 5432) 대응.

## 배포 요약 (Render + Supabase)

1. **Supabase → Database → Connection string → Connection pooler**
   - Host: `*.pooler.supabase.com` (아웃바운드 우회)
   - Port: **6543**
   - SSL mode: `require`
2. Render 서비스 **Environment**:
   - `SQLALCHEMY_DATABASE_URI=postgresql+psycopg://USER:PASSWORD@HOST:6543/DB?sslmode=require`
   - `SECRET_KEY=임의의_난수`
3. Deploy. 첫 부팅 시 DB가 잠깐 안 붙어도 앱이 **크래시하지 않도록** 보호됨.

## 로컬 실행

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export FLASK_DEBUG=1
# DB 미설정 시 sqlite 활용
python app.py
```

## 참고
- `app.py`는 `postgres://` 스킴을 자동으로 `postgresql+psycopg://`로 변환하고, `sslmode=require`를 보장합니다.
- DB 미연결 시에도 500 대신 플래시 메시지를 띄우고 빈 목록을 보여줍니다.
