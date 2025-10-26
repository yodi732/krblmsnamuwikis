# Byeollae Wiki Patch (Legal + Hook)

이 패치는 기존 디자인을 변경하지 않고 다음을 제공합니다.

- `templates/legal/_terms_body.html`: 별내위키 **이용약관 본문**
- `templates/legal/_privacy_body.html`: 별내위키 **개인정보처리방침 본문**
- `templates/legal_terms.html`, `templates/legal_privacy.html`: 각 본문을 include한 페이지
- `apply_patch.py`: `templates/signup.html` 내 “전문 보기” 영역의 자리표시 문구를 **실제 본문 include**로 자동 치환

## 적용 방법

1. 레포지토리 루트에 이 폴더 내용을 그대로 복사/덮어쓰기 합니다.
2. 루트에서 다음 명령을 실행해 자동 치환을 수행합니다.

```bash
python3 apply_patch.py
```

성공 메시지: `signup.html에 전문 include를 삽입했습니다.`

치환이 실패한다면 `templates/signup.html`에서 다음 두 줄을 적절한 위치에 직접 삽입하세요.

```jinja2
{% include "legal/_terms_body.html" %}
{% include "legal/_privacy_body.html" %}
```

## 라우트 (없다면 추가)

```python
@app.route("/legal/terms")
def terms():
    return render_template("legal_terms.html")

@app.route("/legal/privacy")
def privacy():
    return render_template("legal_privacy.html")
```

## 기타

- Render 배포 시 `requirements.txt`에 `gunicorn==23.0.0`이 포함되어야 합니다.
- 하위문서 생성 시 상위문서 드롭다운은 `Document.query.filter_by(parent_id=None)`로 전달하면 상위문서만 노출됩니다.
