# 별내위키 (Flask + Supabase + Render)

## 빠른 배포
1) Supabase → Database → **Connection strings** → **Pooling (Transaction)** URI 복사
2) Render → Environment → `DATABASE_URL` 입력
```
postgresql+psycopg://postgres:<비밀번호>@db.<프로젝트ref>.supabase.co:6543/postgres?sslmode=require&connect_timeout=10
```
3) Render → Settings → Advanced → **Clear build cache** → **Manual Deploy**
4) `/healthz` 확인 → `{"ok": true}`
5) (최초 1회) **POST** `/init-db` → 테이블 생성

## 로컬 실행
```
pip install -r requirements.txt
export DATABASE_URL="sqlite:///local.db"
python app.py
```
