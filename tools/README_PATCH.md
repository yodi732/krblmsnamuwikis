# krblmsnamuwikis 패치 (오류 제거 전용 · 디자인 변경 없음)

이 압축 파일은 **DB 스키마 누락으로 발생한 500 오류**(is_legal, user_email 컬럼 없음)와
`_log_action` 미정의로 인한 오류, 그리고 약관/개인정보처리방침을 DB에서 찾다가 터지는 문제를
**소스만 추가**해서 해결합니다. 기존 템플릿/스타일은 건드리지 않습니다.

## 적용 방법 (레포 루트에 그대로 복사만)

1) 레포지토리 루트에 이 파일들을 그대로 복사(덮어쓰기 X)합니다.
   - `schema_bootstrap.py`
   - `legal_bp.py`
   - `logging_helper.py`
   - `templates/legal/terms.html`
   - `templates/legal/privacy.html`

2) `app.py` 맨 아래쪽(Flask app과 db가 생성된 뒤)에 **딱 3줄만** 추가하세요.

```python
from schema_bootstrap import init_schema_bootstrap
from legal_bp import legal_bp
from logging_helper import _log_action  # 기존 코드에서 _log_action을 호출한다면 이 import만으로 해결됩니다.

init_schema_bootstrap(app, db)      # 앱 시작 시 테이블/컬럼 자동 보강
app.register_blueprint(legal_bp)    # /legal/terms, /legal/privacy 정적 페이지
```

> 위 3~4줄 외에는 어떤 파일도 수정할 필요가 없습니다.
> 디자인/템플릿은 그대로 유지됩니다.

---

## 무엇이 바뀌나요?

- 앱이 기동될 때 자동으로 다음을 수행합니다.
  - `document.is_legal` 컬럼이 없으면 `BOOLEAN DEFAULT FALSE` 로 **자동 추가**
  - `audit_log.user_email` 컬럼이 없으면 `TEXT` 로 **자동 추가**
- `/legal/terms`, `/legal/privacy` 는 **DB를 조회하지 않고** 템플릿 파일로 직접 렌더링
- 기존 라우트에서 호출하던 `_log_action(...)` 이 **정의되어 있지 않아도** 위 import 한 줄로 사용 가능

## 실패할 때는?

- Render 콘솔 로그에 `ALTER TABLE ...` 같은 문구가 보이면 패치가 정상 동작 중입니다.
- 혹시 DB 사용자 권한 문제로 DDL이 막혀 있다면, Render 콘솔에 그 에러가 찍힙니다.
  그 경우엔 저한테 로그만 붙여 주세요. 다른 우회 패치를 드리겠습니다.

---

## 보안/권한

- 컬럼 추가는 `ALTER TABLE` 만 수행하며, 드랍/데이터 손상 작업은 없습니다.
- 약관/개인정보는 템플릿 두 파일만 사용하므로, 위키 문서와 별도로 안전합니다.