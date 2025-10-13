# 별내위키 (오류 원인 고친 배포본)
- PostgreSQL `DATABASE_URL` 사용. 필요 시 `postgresql+psycopg://`로 자동 보정.
- 최초 요청 시 자동 마이그레이션: `document.author_id`, `document.created_at` 없으면 추가.
- @bl-m.kr 도메인만 회원가입/로그인, 비번 해시 저장, 일 10회 로그인 실패 제한.
- 문서 CRUD는 로그인 사용자만. 로그에는 이메일 표시.
- 회원 탈퇴(`/delete-account`): 개인정보 삭제 + 작성자 표기 제거(문서 본문은 유지).
- 하단 푸터는 좌하단 고정: "피드백 → 메일 · 개인정보처리방침 · 이용약관"
