# Patch: 회원가입/로그인/탈퇴 + 약관/개인정보 동의 + 문서 CRUD 보호

이 ZIP은 기존 프로젝트 루트에 *그대로 덮어쓰기* 하면 됩니다.

## 들어있는 것
- `app.py` : 사용자/동의/로그 모델과 인증 라우트를 추가하고, 문서 생성/수정/삭제는 로그인 사용자만 가능하도록 보호했습니다.
- `templates/signup.html`, `templates/login.html`, `templates/account.html`, `templates/_auth_nav.html`
- `requirements.txt` : `Flask-Login` 추가

## 적용 순서 (Render 포함)
1) **코드 반영**
   - 이 ZIP의 파일을 기존 코드에 덮어씌웁니다. (특히 `app.py`와 새 템플릿)
2) **환경변수**
   - (변경 없음) `DATABASE_URL` 사용.
3) **패키지 설치**
   - Render라면 자동 빌드 시 `Flask-Login`이 설치됩니다.
4) **초기 약관/개인정보 문서 자동 생성**
   - 앱이 부팅될 때 slug=`terms`, `privacy` 문서를 자동으로 생성(없을 때만)합니다.
   - 내용은 템플릿 문자열이 들어가며, 나중에 위키에서 자유롭게 수정하세요.
5) **헤더에 로그인/회원가입 링크 표시**
   - `base.html`의 네비게이션 영역 안쪽 적절한 위치에 `{% include "_auth_nav.html" %}` 한 줄만 추가하세요.
   - 스타일을 건드리지 않기 위해 *기존 마크업은 유지*하고 링크만 삽입합니다.
6) **권한**
   - 문서 *보기*는 누구나 가능.
   - 문서 *만들기/수정/삭제*는 로그인 필요.
   - 로그 페이지(`/logs`)는 로그인 필요(추가로 관리자만 보게 하려면 `User.is_admin`을 True로 바꾸세요).

## 데이터베이스
- 새 테이블: `user`, `user_consent`, `terms_version`, `log`(기존 유지), `document`(기존 유지)
- 사용자 비밀번호는 `werkzeug.security`의 `generate_password_hash`로 해시 저장.

---

문제 생기면 `FLASK_DEBUG=1`로 재배포 후 로그를 확인해 주세요.
