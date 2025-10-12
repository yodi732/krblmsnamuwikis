# 별내위키 (Flask)

- 학교 이메일(@bl-m.kr)만 회원가입 가능
- 이메일 인증, 비밀번호 재설정(토큰, 24시간 유효)
- 로그인 실패 일 10회 제한
- 문서 CRUD (로그인 필요), 로그에는 IP 대신 이메일 기록
- 회원탈퇴: 계정/개인정보 즉시 삭제, 문서는 작성자만 익명화(SET NULL)

## 환경변수
- `DATABASE_URL` (Postgres 또는 sqlite:///app.db)
- `SECRET_KEY`
- (선택) SMTP 메일 발송
  - `SMTP_HOST`, `SMTP_PORT`(기본 587), `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`

## 실행
```
pip install -r requirements.txt
flask --app app.py init-db
flask --app app.py run
```
