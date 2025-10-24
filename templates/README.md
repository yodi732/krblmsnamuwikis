
# 별내위키 기능 추가 미니 패치 (쌓아올리기 방식)

이 패치는 **기존 디자인을 그대로 유지**하면서 아래 8개 기능을 추가합니다.

1. 문서 삭제 (홈 목록 옆 삭제 버튼 + 확인 모달/확인창)
2. 로그 보기 (/logs – 관리자만)
3. 문서 생성 시 상위/하위 문서 선택 기능 (라디오 + 부모 드롭다운)
4. 회원탈퇴 (비밀번호 확인 후 탈퇴)
5. 홈 버튼 (네비게이션 공용 partial 추가)
6. 홈에서 상/하위 문서 구조를 트리로 보기
7. 회원가입 화면 안내문: “학교 계정 (@bl-m.kr)만 가입 …” + 이메일 placeholder 예시(1234@bl-m.kr)
8. 회원가입 비밀번호 재입력(확인) 필드 및 서버 검증

> **중요**: 패치는 “쌓아올리기” 방식입니다. 기존 파일을 대체하지 않고,  
> - 새 Blueprint(`patch_feature.py`)를 추가해 라우트를 보강하고,  
> - 추가 템플릿(components/*, patch/*)과 JS만 더합니다.  
> - 기존 템플릿은 건드리지 않습니다. (필요 시 include 한 줄만 추가)

---

## 0) 적용 요약 (딱 2줄 + 1줄)

`app.py` (혹은 Flask 앱 팩토리 파일)에 아래 2줄을 추가하세요.

```python
from patch_feature import patch_bp
app.register_blueprint(patch_bp)
```

정적 파일 버스팅을 위해 (선택) **base.html**의 `</body>` 바로 위에 한 줄 추가:

```html
<script src="{{ url_for('static', filename='patch/patch.js') }}"></script>
```

---

## 1) 폴더 구조

```
patch_feature.py                  # 새 Blueprint (라우트/폼/권한)
templates/
  components/
    delete_button_inline.html     # 삭제 버튼(목록/상세 공용), 확인창
    navbar_home.html              # 홈 버튼 partial
    doc_tree.html                 # 트리 렌더링 partial
  patch/
    create_document_extra.html    # 생성 폼에 상/하위 선택 필드
    account_delete.html           # 회원탈퇴 화면
    logs.html                     # 서버 로그(최근 n줄) 뷰 (관리자)
    signup_extra_fields.html      # 회원가입 추가 필드/안내 partial
static/patch/patch.js             # 삭제 확인/폼 유틸
migrations/optional_sql.sql       # 컬럼/제약 조건 보강 SQL (옵션)
```

---

## 2) 통합 가이드 (템플릿 쌓아올리기)

### 2-1) 홈 버튼 추가
기존 네비게이션 템플릿에 아래 한 줄을 **원하는 위치**에 추가하세요.

```jinja2
{% include "components/navbar_home.html" %}
```

### 2-2) 홈 목록에서 삭제 버튼 보이기
홈(문서 목록) 템플릿의 각 문서 행 안에서 제목 링크 옆에 넣어주세요.

```jinja2
{% set _doc = d %}
{% include "components/delete_button_inline.html" %}
```

> `_doc` 변수에 해당 문서 객체를 넣어주면 됩니다. (상세 화면에서도 동일하게 사용 가능)

### 2-3) 문서 생성 폼에 상/하위 선택 필드 쌓기
문서 생성 폼 템플릿 하단(제출 버튼 위쪽 권장)에 다음을 추가:

```jinja2
{% include "patch/create_document_extra.html" %}
```

> 서버에서는 본 패치의 Blueprint가 `parent_id`와 `position_mode` 값을 처리합니다.
> 원 앱의 생성 라우트를 그대로 쓰는 경우, patch_feature의 `/document/create`를 사용하도록 링크를 바꿔도 됩니다.

### 2-4) 회원가입 화면에 추가 안내/필드 쌓기
회원가입 템플릿에서 이메일 입력 영역 근처에 다음을 추가:

```jinja2
{% include "patch/signup_extra_fields.html" %}
```

### 2-5) 회원탈퇴 메뉴 연결
마이페이지/설정 메뉴 등에 아래 링크를 노출하세요.

```jinja2
<a href="{{ url_for('patch.account_delete') }}">회원탈퇴</a>
```

---

## 3) 백엔드(권한/DB) 메모

- **관리자 판별**: `User.is_admin`(Boolean)이 있다고 가정합니다.
  - 없으면 `migrations/optional_sql.sql`로 추가하세요.
- **Document 모델**: `parent_id`(nullable, FK) 가정. 없으면 동일 SQL에 스키마 보강 예시가 있습니다.
- 삭제는 `POST /document/<id>/delete` 로 동작합니다. CSRF 미사용 환경 기준.
- 로그 보기: Render 같은 환경은 앱 프로세스 표준 로그를 파일로 남기지 않는 경우가 많습니다.  
  본 패치는 환경변수 `APP_LOG_PATH` (없으면 `app.log`) 파일에서 **마지막 N=500줄**만 읽습니다.

---

## 4) 보안 메모

- 삭제/생성/탈퇴는 반드시 로그인 필요. 관리자 구간(/logs)은 `is_admin=True` 필요.
- 회원가입 시: 이메일 도메인 `@bl-m.kr` 강제, 비밀번호 확인 일치 검사.

---

## 5) 문제 해결

- 405(Method Not Allowed): 템플릿 버튼이 GET으로 호출되면 발생합니다. 본 패치의 버튼은 **POST** 폼으로 되어 있습니다.
- 'current_user' undefined: Flask-Login으로 전달되지 않는 템플릿에서 발생할 수 있습니다. 본 패치는 `g.user`와 호환되게 동작합니다.

행운을 빕니다! 필요한 부분은 더 확장해 드릴게요.
