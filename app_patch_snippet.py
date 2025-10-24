# --- 문서 삭제 라우트 패치 (붙여넣기) ---
from flask import abort, flash, redirect, url_for
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

@app.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)

    # 시스템 문서는 삭제 금지
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
