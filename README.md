# 별내위키 배포 번들

## 1) 환경 변수
- `DATABASE_URL` : Render의 PostgreSQL URL (sslmode=require 유지)
- `SECRET_KEY` : 세션 키

## 2) 배포 (Render 권장)
- New > Web Service > Connect Repo 없이 "Static/Dockerless" 선택 후 이 번들 업로드해도 되며,
  보통은 깃 저장소로 올린 뒤 Render가 빌드합니다.
- Build Command: *(없음)*
- Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`

## 3) 마이그레이션(자동/수동)
앱은 부팅 시 다음을 자동 실행합니다.
- `ALTER TABLE "user" ADD COLUMN IF NOT EXISTS pw_hash VARCHAR;`
- `ALTER TABLE "user" ALTER COLUMN created_at SET DEFAULT NOW();`
- `ALTER TABLE document ALTER COLUMN updated_at SET DEFAULT NOW();`

그래도 수동이 필요하면 psql에서 아래를 실행:
```sql
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS pw_hash VARCHAR;
ALTER TABLE "user" ALTER COLUMN created_at SET DEFAULT NOW();
ALTER TABLE document ALTER COLUMN updated_at SET DEFAULT NOW();
```

## 4) 기능
- 홈: 나무위키처럼 계층을 "한 리스트"로 들여쓰기 표시 (최근 변경 제거)
- 로그인: 약관/정책 요약 제거
- 회원가입: 체크박스 정렬, 약관/정책 요약 + 전문 보기 링크
- 문서 만들기/보기, 시스템 문서(/terms, /privacy) 라우팅
- 회원탈퇴: `/delete_account` POST (즉시 삭제)

## 5) 개인정보 보호 메모
- 비밀번호는 `werkzeug.security.generate_password_hash()`로 해시 저장
- 로그인은 해시 검증 실패/컬럼 없음 등 모든 경우 사용자 친화 메시지로 처리
