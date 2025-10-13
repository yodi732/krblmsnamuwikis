
# 별내위키 (오류 수정판)

- 파란 배너 상단 UI, "로그 보기" 버튼 추가
- 회원가입 체크박스(동의해야 가입 가능), 라벨 "학교 계정 이메일", placeholder `abcd@bl-m.kr`
- 도메인 제한: 기본 `@bl-m.kr` (환경변수 `ALLOWED_EMAIL_DOMAIN` 로 변경 가능)
- 이메일 인증/비밀번호 재설정: 실제 SMTP 사용 (환경변수 필요)
- 로그 페이지: 이메일/행동/세부/시간 표기
- "회원탈퇴"는 로그인 상태에서만 표시

## 환경 변수
```
SECRET_KEY=랜덤값
DATABASE_URL=postgresql://...
ALLOWED_EMAIL_DOMAIN=@bl-m.kr

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
SMTP_FROM=no-reply@bl-m.kr

# 배포 URL(메일 본문 절대주소에 사용)
EXTERNAL_BASE_URL=https://krblmsnamuwikis.onrender.com
```
## 배포
```
pip install -r requirements.txt
gunicorn app:app --bind 0.0.0.0:8000
```
