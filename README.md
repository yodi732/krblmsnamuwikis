
# Mini Patch — Document Delete (no design change)

이 패치는 **문서 삭제 기능**만 추가합니다. 디자인은 변경하지 않고, 목록의 각 문서 **오른쪽**에 '삭제' 버튼이 보입니다.
삭제 버튼을 누르면 **브라우저 확인 대화상자**가 한 번 더 뜹니다.

## 1) app.py에 라우트 추가
아래 코드를 `app.py`의 라우트 섹션 아무 곳에 추가하세요. (가급적 파일 하단 쪽)
중복 import가 보이면 제거해도 됩니다.

```python
# --- 문서 삭제 ---
from sqlalchemy.exc import IntegrityError
from flask import request, abort, flash, redirect, url_for
from flask_login import login_required

@app.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)

    # 시스템 문서는 삭제 금지 (이용약관/개인정보처리방침 등)
    if getattr(doc, "is_system", False):
        abort(403)

    try:
        db.session.delete(doc)
        db.session.commit()
        flash("문서를 삭제했습니다.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("문서를 삭제할 수 없습니다. 관련 데이터가 남아 있을 수 있어요.", "danger")

    return redirect(url_for("index"))
```

## 2) 템플릿에 버튼 포함시키기 (목록 화면)
문서 목록을 뿌리는 반복문(예: `{% for d in docs %}`) **안에서**, 각 문서 행의 **오른쪽 끝**에 다음 한 줄을 추가하세요.

```jinja2
{% include "components/delete_button.html" with context %}
```

> 위 한 줄은 **반드시** 각 문서 `d`를 참조할 수 있는 영역(반복문 내부)에 넣어주세요.

### 버튼이 오른쪽에 붙도록 하는 방법
컴포넌트 내부에 `style="float:right"` 를 넣어둬서 별도 CSS 변경이 필요 없습니다.
만약 flex 레이아웃을 쓰고 있으면, 그 컨테이너 오른쪽 영역(예: 액션 칼럼) 쪽에 include 하시면 됩니다.

## 3) 템플릿(상세 화면)에 버튼 추가(선택)
상세 보기 페이지에서도 삭제를 노출하려면, 문서 객체 이름이 `doc`일 때 아래 한 줄만 넣으면 됩니다.

```jinja2
{% with d=doc %}{% include "components/delete_button.html" %}{% endwith %}
```

## 4) 확인
1. 로그인 후 일반 문서에만 '삭제' 버튼이 보이는지
2. 버튼 클릭 → 확인창 → 삭제 완료 플래시 후 목록으로 이동
3. 시스템 문서(약관/정책)는 버튼 미노출, 직접 POST 시 403

## 파일 설명
- `app_patch_snippet.py` : 1)에서 복붙할 라우트 코드 원문
- `templates/components/delete_button.html` : 삭제 버튼 컴포넌트(확인창 포함)
- 이외 파일/디자인은 그대로 둡니다.
