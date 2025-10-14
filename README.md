# 별내위키 (고쳐진 버전)

이 번들에는 다음이 포함됩니다.

- DB 스키마 자동 보정(부트스트랩): `audit_log` 테이블 생성/보강, `document.updated_at` 누락시 추가
- 상위/하위 문서 생성 UI 및 제약(하위의 하위 금지)
- 감사 로그: 대상=**편집자 이메일**, 세부=문서 제목
- 삭제 버튼: 빨간 글씨 텍스트(배경 없음)
- 회원가입: 약관 문구 한 줄 + 체크박스 우측, 비밀번호 표시 버튼
- 로그인이 되어 있으면 상단에 로그보기/문서 만들기/수정/삭제/회원탈퇴 버튼 표시

## 실행

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 환경변수 (Render의 DATABASE_URL 또는 로컬 SQLite 사용)
export DATABASE_URL=sqlite:///app.db  # 로컬 테스트용
export SECRET_KEY="change-this"

flask --app app run -p 5000 --debug
```

Render에선 `web: gunicorn app:app --bind 0.0.0.0:$PORT` 로 기동됩니다.

## DB 마이그레이션(자동)

앱 부팅 시 `bootstrap_db()` 가 아래를 수행합니다.
- `audit_log(actor, action, target, created_at)` 없으면 생성, 누락 컬럼 보강
- `document.updated_at` 없으면 추가

