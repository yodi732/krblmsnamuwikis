# 별내위키 (Byeollae Wiki)

Flask + PostgreSQL 기반의 간단한 위키. Render 배포에 최적화되어 있습니다.

## 로컬 실행
```bash
python -m venv .venv && source .venv/bin/activate  # Windows는 .venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///local.db
export SECRET_KEY=dev
python app.py
```

## Render 배포

- **Build Command**
  ```
  pip install -r requirements.txt
  ```

- **Start Command**
  ```
  gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
  ```

- **Environment Variables**
  - `DATABASE_URL`: Render Postgres에서 발급된 URL (예: `postgres://user:pass@host:5432/db`)
    - 앱에서 자동으로 `postgresql+psycopg://`로 변환됩니다.
  - `SECRET_KEY`: 임의의 랜덤 문자열

## 기능
- 회원가입/로그인/로그아웃(해시 저장)
- 약관/개인정보 처리방침 **자동 시드**
- 문서 CRUD + 1단계 상하위 구조
- 계정 삭제(탈퇴) 기능

## 주의
- 템플릿 공통 레이아웃 파일명은 `_base.html` 입니다.
- `Document.title` 은 유니크 인덱스입니다(중복 생성 방지).
```
