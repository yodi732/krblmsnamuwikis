
별내위키 — 미니 패치 (삭제 버튼/로그 보기/회원가입 안내·재확인)

이 패치는 "쌓아올리는" 방식으로 기존 디자인을 보존합니다.
아래 순서대로 반영하세요.

────────────────────────────────────────
1) 파일 복사
────────────────────────────────────────
다음 파일을 여러분 프로젝트 루트에 그대로 복사(덮어쓰기 X, 새로 추가)합니다.

- templates/logs.html
- PATCH_README.txt (이 문서)
- app_snippets_delete_and_logs.py  (app.py에 붙여넣을 코드 블럭)
- templates/signup_snippet.html     (signup 템플릿에서 추가할 폼 조각)
- templates/index_row_delete_button_snippet.html (index 템플릿에서 각 문서 행에 넣을 삭제 버튼 조각)

※ 'index.html' 전체를 교체하지 않습니다. 귀하의 index 템플릿에서
  각 문서 row 안쪽(시간 오른쪽)에 아래 조각을 그대로 삽입하세요:
  -> templates/index_row_delete_button_snippet.html

※ 'signup.html' 전체를 교체하지 않습니다. 귀하의 signup 템플릿 폼 안에
  아래 조각을 그대로 삽입하세요:
  -> templates/signup_snippet.html

────────────────────────────────────────
2) app.py 수정 (필수, 3군데)
────────────────────────────────────────
아래 파일의 세 코드 블럭을 app.py에 추가합니다:
- app_snippets_delete_and_logs.py

[위치 A] import 근처에 추가:
------------------------------------------------------------
from datetime import datetime
import os, json
------------------------------------------------------------

[위치 B] 앱 파일 어딘가(함수 외부)에 감사 로그 헬퍼 추가:
------------------------------------------------------------
AUDIT_LOG = os.path.join(os.path.dirname(__file__), "audit.log")

def _audit(action, user_email, doc_id=None, title=None):
    try:
        rec = {
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "user": getattr(getattr(g, "user", None), "email", None),
            "action": action,  # create / update / delete
            "doc_id": doc_id,
            "title": title,
        }
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
------------------------------------------------------------

[위치 C] 라우트 추가 (파일 하단 쪽에 두면 편합니다):
------------------------------------------------------------
@app.post("/document/<int:doc_id>/delete")
def delete_document(doc_id):
    if not g.user:
        abort(403)
    doc = Document.query.get_or_404(doc_id)
    if getattr(doc, "is_system", False):
        flash("시스템 문서는 삭제할 수 없습니다.", "warning")
        return redirect(url_for("index"))

    db.session.delete(doc)
    db.session.commit()

    _audit("delete", user_email=g.user.email, doc_id=doc_id, title=doc.title)
    flash("문서를 삭제했습니다.", "success")
    return redirect(url_for("index"))

@app.get("/logs")
def view_logs():
    if not g.user:
        abort(403)
    logs = []
    if os.path.exists(AUDIT_LOG):
        with open(AUDIT_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    logs.append(json.loads(line))
                except:
                    continue
    return render_template("logs.html", logs=reversed(logs))
------------------------------------------------------------

추가로, 문서 생성/수정 처리 끝에 아래 한 줄을 각각 넣어두면 감사 로그가 남습니다.
------------------------------------------------------------
_audit("create", user_email=g.user.email, doc_id=new_doc.id, title=new_doc.title)
_audit("update", user_email=g.user.email, doc_id=doc.id, title=doc.title)
------------------------------------------------------------

────────────────────────────────────────
3) index.html(홈 목록) — 삭제 버튼 삽입
────────────────────────────────────────
각 문서 row 내부(시간 표시 오른쪽)에 다음 조각을 넣습니다.

(파일) templates/index_row_delete_button_snippet.html
------------------------------------------------------------
<form action="{{ url_for('delete_document', doc_id=d.id) }}" method="post" style="display:inline" onsubmit="return confirm('정말 삭제할까요? 되돌릴 수 없습니다.');">
  <button type="submit" class="btn btn-xs">삭제</button>
</form>
------------------------------------------------------------

※ 오른쪽 정렬이 필요하면 해당 row 컨테이너를
  display:flex; justify-content:space-between; align-items:center;
  형태로 잡아 주세요(기존 스타일을 건드리지 않게 row에만 적용).

────────────────────────────────────────
4) signup.html — 도메인 안내 + placeholder + 비밀번호 재확인
────────────────────────────────────────
(파일) templates/signup_snippet.html  내용을 여러분의 signup 폼에 ‘쌓아’ 넣으세요.

또한 /signup POST 처리에서 아래 검증을 추가하세요:
------------------------------------------------------------
email = request.form.get("email","").strip().lower()
password = request.form.get("password","")
password2 = request.form.get("password2","")

if not email.endswith("@bl-m.kr"):
    flash("학교 계정(@bl-m.kr)만 가입할 수 있습니다.", "warning")
    return render_template("signup.html")

if password != password2:
    flash("비밀번호가 일치하지 않습니다.", "warning")
    return render_template("signup.html")
------------------------------------------------------------

────────────────────────────────────────
5) 로그 보기 메뉴
────────────────────────────────────────
상단 네비게이션 어딘가에 다음 링크만 추가하면 됩니다:
<a href="{{ url_for('view_logs') }}">로그</a>

────────────────────────────────────────
완료입니다. 배포 후 브라우저에서 강력 새로고침(Ctrl+F5)을 권장합니다.
