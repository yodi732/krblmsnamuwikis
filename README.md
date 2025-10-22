# 별내위키 (배포용 패치)

- 보기 전용 **이용약관/개인정보처리방침** 제공 (`/legal/terms`, `/legal/privacy`)
- 문서 목록/편집/삭제에서 **법정 문서 제외**
- 회원가입 화면에서 **필수 2체크**(마케팅 없음)
- DB 스키마 보호: `user.pw`, `audit_log.doc_title`, `document.is_legal` 자동 보강
- `wsgi:app`로 구동 (Render/Heroku 대응)

## 실행
```bash
pip install -r requirements.txt
export FLASK_ENV=production
export SECRET_KEY=change-me
# 로컬 SQLite 사용 시 그대로. Postgres 사용 시 DATABASE_URL 환경변수 설정
gunicorn wsgi:app --bind 0.0.0.0:8000
```

## 참고
- 기존 테이블이 있을 때도 안전하게 동작하도록 `ALTER TABLE IF NOT EXISTS`를 사용합니다.
