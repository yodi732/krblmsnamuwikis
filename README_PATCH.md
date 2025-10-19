# 별내위키 – UI 패치 & 로그인 500 오류 핫픽스 (배포용 ZIP)

이 ZIP은 **템플릿/스타일만 교체**하고 DB에 **`pw_hash` 컬럼을 추가**하는 패치입니다.
애플리케이션 파이썬 코드는 건드리지 않고, 즉시 배포 가능한 형태입니다.

## 포함 파일
- `templates/_layout.html` : 홈 버튼 복구, 네비게이션/버튼 톤 업그레이드
- `templates/home.html` : 나무위키처럼 상·하위 문서를 한 뷰에서 트리로 표시
- `templates/login.html` : 약관/방침 박스 제거, 간결한 로그인 폼
- `templates/signup.html` : 체크박스 문구 한 줄·마침표 제거, 요약+전문 보기 상자 유지
- `static/style.css` : 버튼 테두리 제거, 여백/그림자/포커스 링 개선, 트리 스타일
- `MIGRATION_pw_hash.sql` : 로그인 500 (UndefinedColumn: `user.pw_hash`) 해결용

## 적용 순서
1) **Render / Git 저장소**의 기존 파일을 그대로 두고, 이 ZIP의 `templates`와 `static`만 **덮어쓰기** 합니다.  
   (리포지토리에 커밋 → Render가 자동 배포)

2) **DB 스키마 핫픽스** (한 번만 실행)
   ```sql
   -- 컬럼이 없을 때만 추가
   DO $$
   BEGIN
     IF NOT EXISTS (
       SELECT 1 FROM information_schema.columns
       WHERE table_name='user' AND column_name='pw_hash'
     ) THEN
       ALTER TABLE "user" ADD COLUMN pw_hash VARCHAR(255);
     END IF;
   END $$;
   ```
   - Render 콘솔 → PostgreSQL 연결 정보로 `psql` 접속 후 붙여넣기
   - 가입 로직이 `pw_hash`에 해시를 저장하므로, 컬럼만 있으면 로그인 500이 사라집니다.

3) (선택) 기존 가입 데이터가 있고, 다른 컬럼(`password_hash` 등)을 쓰고 있었다면
   - 앱의 저장 로직을 확인하여 `pw_hash`에 저장되도록 고치거나,
   - 아래처럼 한 번에 복사합니다.
   ```sql
   UPDATE "user" SET pw_hash = COALESCE(pw_hash, password_hash);
   ```

## 확인 체크리스트
- [ ] 홈 버튼이 좌측 상단에 보이고 동작한다.
- [ ] 버튼 테두리(검정) 없음, 입력칸-버튼 간 여백이 충분하다.
- [ ] 홈에서 상·하위 문서가 한 뷰에서 들여쓰기(라인 포함)로 명확히 보인다.
- [ ] 회원가입 폼의 동의 문구 두 줄 → 한 줄, 마침표 없음, 체크박스가 문구 오른쪽에 밀착.
- [ ] 로그인 페이지에 약관/방침 본문 박스가 나오지 않는다.
- [ ] `/create`, `/logs` 접근 시 로그인하지 않았으면 로그인 페이지로 302 이동한다.
- [ ] 로그인 시 더 이상 500이 발생하지 않는다. (DB에 `pw_hash` 존재)

## 개인정보처리방침 반영 포인트 (요약)
- 수집항목 최소화(학교 이메일, 해시화된 비밀번호, 운영 로그)
- 이용목적 명확화(인증/운영/보안)
- 보관·파기(탈퇴 즉시 계정 삭제, 법정 보관 로그는 기간 후 파기)
- 제3자 제공/국외 이전 없음
- 정보주체 권리 및 행사 방법 고지
- 안전성 확보 조치(암호화/최소권한/접근통제)

궁금한 점이 있으면 언제든 이슈 주세요!
