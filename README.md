# 별내위키(학교 도메인 전용)

이 패키지는 다음을 포함합니다.
- 회원가입(학교 도메인 `@bl-m.kr`만 허용) + 약관 동의
- 이메일 인증 / 비밀번호 재설정
- 로그인 실패 일일 10회 제한
- 문서 만들기/삭제(학교 구성원 + 이메일 인증자만)
- 로그에 **IP 대신 이메일**을 남김
- 개인정보처리방침/이용약관 페이지
- 푸터를 좌측 하단 고정: `피드백 → lyhjs1115@gmail.com · 개인정보처리방침 · 이용약관`

## 1) 배포/로컬 실행

### Render(권장)
1. Render PostgreSQL 생성 후 `DATABASE_URL` 확보
2. 새 Web Service 생성 → 이 저장소 zip 업로드
3. 환경 변수 추가
   - `DATABASE_URL` : (Render PG 접속 문자열)
   - `SECRET_KEY` : (아무 문자열)
   - `SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM` (메일 발송용. 없으면 콘솔에 워닝 출력만 하고 작동은 계속됨)
4. 첫 배포 후, 웹 콘솔에서:
   - (데이터가 없다면) 아무것도 하지 않아도 `create_all()`이 테이블을 생성
   - (기존 테이블이 있고 컬럼이 부족하면) Render PG 콘솔에서 `sql/manual_migration.sql` 내용을 실행

### 로컬
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///app.db
export SECRET_KEY=dev
flask --app app.py init-db
python app.py
```

## 2) 운영 체크리스트
- 이메일 인증 메일/비번 재설정 메일이 정상 발송되는지(SMTP 설정)
- 로그인 실패 제한 수치: 기본 10회/일 (코드 상수 `MAX_LOGIN_FAILS_PER_DAY`)
- 개인정보처리방침/이용약관 내용 확인 및 필요시 텍스트 수정(`templates/privacy.html`, `templates/terms.html`)

## 3) 회원탈퇴
- 로그인 후 상단 메뉴 **계정** → 페이지 하단 **회원탈퇴** 버튼
- 탈퇴 시: 토큰/개인데이터 삭제, 문서 `author_id`는 NULL 처리(작성물은 보존)

## 4) 스키마가 맞지 않아 500이 날 때
로그에 `column user.password does not exist`, `column document.author_id does not exist` 등 메시지가 보이면
`sql/manual_migration.sql`을 DB에서 실행하거나, 데이터가 비어 있다면 테이블을 드롭 후 앱을 재시작하세요.
