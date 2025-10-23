# 별내위키 패치

- 자동 마이그레이션
  - `document.body` -> `document.content` 로 자동 변경
  - `"user".is_admin` 컬럼이 없으면 자동 추가 (BOOLEAN NOT NULL DEFAULT FALSE)
- 약관/개인정보처리방침: 보기 전용, 목록 비노출
- 회원가입 화면에서 **전문 보기** 즉시 확인 가능 (details)
- 푸터 변경: `피드백 & 문의 -> lyhjs1115@gmail.com`

## 배포
1) 환경변수: `DATABASE_URL`, `SECRET_KEY`
2) 업로드 후 부팅되면 자동 마이그레이션이 1회 실행됩니다.
