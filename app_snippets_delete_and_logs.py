# ===== app.py에 추가할 코드 조각 모음 =====
from datetime import datetime
import os, json

AUDIT_LOG = os.path.join(os.path.dirname(__file__), "audit.log")

def _audit(action, user_email, doc_id=None, title=None):
    try:
        rec = {
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "user": user_email,
            "action": action,  # create / update / delete
            "doc_id": doc_id,
            "title": title,
        }
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass

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

# (선택) 생성/수정 시 처리 끝에 아래 한 줄 추가:
# _audit("create", user_email=g.user.email, doc_id=new_doc.id, title=new_doc.title)
# _audit("update", user_email=g.user.email, doc_id=doc.id, title=doc.title)
