# 별내위키 (Auth + Verify + Password Reset + Privacy/Terms Consent)
- 회원가입/로그인, 이메일 인증, 비밀번호 재설정
- 회원가입 시 개인정보처리방침 및 이용약관 **동의 필수**(체크)
- 동의 일시 `User.agreed_at` 저장 (자동 스키마 보정)
- 푸터에 **개인정보처리방침(/privacy)**, **이용약관(/terms)** 링크 노출
- psycopg3, 자동 URL 정규화, 기존 DB 자동 스키마 보정
