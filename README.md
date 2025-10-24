
# byeollae_wiki_feature_patch_v2

이 패치는 기존 디자인을 **수정하지 않고 쌓아올리는 방식**으로 다음을 제공합니다.

- 문서 삭제(홈/상세 인라인 버튼, 재확인 팝업)
- 문서 생성시 상위/하위 선택 + 부모 문서 선택 드롭다운 (템플릿 partial)
- 홈 버튼 partial, 트리 렌더링 partial
- 회원탈퇴 화면/라우트
- **로그 보기**(로그인한 사용자 누구나 접근 가능) + **감사 로그 기록**(문서 생성/수정/삭제 시 `email, action, title, id, timestamp` 기록)
- 회원가입 화면: `@bl-m.kr` 안내 문구 + `1234@bl-m.kr` placeholder + 비밀번호 재입력 필드

## 0) app.py에 꼭 2줄 추가 (반드시 필요)
```python
from patch_feature import patch_bp
app.register_blueprint(patch_bp)
```
> 기존 코드 어느 위치든 Flask 앱 `app` 생성 뒤, 다른 등록들 옆에 추가하세요.

---

## 1) 템플릿에 붙이는 법 (쌓아올리기)
- **홈 삭제 버튼**(문서 제목 옆):
```jinja2
{% set _doc = d %}
{% include "components/delete_button_inline.html" %}
```
- **문서 상세 상단(삭제 버튼)**:
```jinja2
{% set _doc = doc %}
{% include "components/delete_button_inline.html" %}
```
- **문서 생성 폼 추가 필드**(제출버튼 위):
```jinja2
{% include "patch/create_document_extra.html" %}
```
- **회원가입 폼 추가 필드**(이메일/비밀번호 묶음 근처):
```jinja2
{% include "patch/signup_extra_fields.html" %}
```
- **홈 버튼**(네비게이션 영역 등 원하시는 곳):
```jinja2
{% include "components/navbar_home.html" %}
```
- (선택) **트리 뷰**:
```jinja2
{% include "components/home_tree.html" %}
```

## 2) 정적 스크립트 로딩 (선택)
`base.html`의 `</body>` 바로 위에:
```html
<script src="{{ url_for('static', filename='patch/patch.js') }}"></script>
```

## 3) 접근 권한
- `/logs` : **로그인**만 되어 있으면 접근 가능(관리자 한정 아님).
- 삭제/회원탈퇴 라우트는 POST만 허용. 프론트에서 confirm 1번 더.

## 4) 감사 로그 파일
- 경로: 환경변수 `APP_AUDIT_LOG`가 있으면 그 경로, 없으면 `audit.log` (앱 루트).
- 포맷: `2025-10-24T07:12:34Z | user@example.com | create|update|delete | doc_id=1 | title=문서제목`

> 기존 앱에 `db`, `Document` 모델이 있으면 자동 SQLAlchemy 이벤트 후킹으로 `insert/update/delete`를 기록합니다.
> 모델 경로가 다르면 `patch_feature.py` 상단의 `try import` 부분을 적절히 고쳐 쓰시면 됩니다.

## 5) 회원탈퇴
- GET `/account/delete` : 안내 및 `DELETE` 확인 입력
- POST 동일 경로: 세션 종료 + 사용자를 비활성화/삭제(프로젝트에 맞게 수정 Hook 제공)

## 6) 배포 이슈 405(DELETE) 방지
- 모든 삭제/탈퇴는 **POST** 폼 전송으로 처리합니다.

---

### 파일 구성
- `patch_feature.py` : Blueprint + 감사로그 + 로그뷰 + 탈퇴 라우트
- `templates/components/delete_button_inline.html`
- `templates/components/navbar_home.html`
- `templates/components/home_tree.html`
- `templates/patch/create_document_extra.html`
- `templates/patch/signup_extra_fields.html`
- `static/patch/patch.js`
