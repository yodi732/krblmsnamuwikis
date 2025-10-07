# 별내위키 (Supabase Ready)

Render + Supabase에서 초기화 없이 실행되도록 만든 최소 스켈레톤.

## 배포
1) GitHub에 올림
2) Render에서
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
3) Environment에 `DATABASE_URL` 추가  
   예시:
   `postgresql+psycopg://postgres:<비번>@db.<ref>.supabase.co:6543/postgres?sslmode=require&connect_timeout=10`
4) Save → Clear build cache → Manual Deploy
