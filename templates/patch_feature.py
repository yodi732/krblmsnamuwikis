
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app, g
from datetime import datetime
import os

patch_bp = Blueprint("patch", __name__)

# --- helpers ---
def _is_logged_in():
    # 호환: g.user 또는 current_user 사용 가능
    u = getattr(g, "user", None)
    return bool(u)

def _user():
    return getattr(g, "user", None)

def _is_admin():
    u = _user()
    return bool(getattr(u, "is_admin", False))

def _db_sess():
    # 원 앱의 db 세션을 전역으로 노출했다고 가정 (e.g. from app import db)
    try:
        from app import db
        return db.session, db
    except Exception:
        return None, None

def _Document():
    try:
        from app import Document
        return Document
    except Exception:
        return None

def _User():
    try:
        from app import User
        return User
    except Exception:
        return None

# --- routes ---

@patch_bp.route("/document/create", methods=["GET","POST"])
def create_document():
    """상/하위 문서 선택을 포함한 문서 생성 라우트(옵션).
    원 앱의 생성 라우트를 대체하지 않으며, 병행 사용 가능합니다.
    """
    if not _is_logged_in():
        flash("로그인이 필요합니다.", "error")
        return redirect(url_for("login") if "login" in current_app.view_functions else url_for("index"))

    Document = _Document()
    if Document is None:
        abort(500)

    session, db = _db_sess()
    if session is None:
        abort(500)

    if request.method == "POST":
        title = request.form.get("title","").strip()
        body = request.form.get("body","").strip()
        position_mode = request.form.get("position_mode","top")  # 'top' or 'child'
        parent_id = request.form.get("parent_id")
        parent = None
        if position_mode == "child" and parent_id:
            try:
                parent = session.get(Document, int(parent_id))
            except Exception:
                parent = None

        if not title:
            flash("제목을 입력하세요.", "error")
            return redirect(request.url)

        doc = Document(title=title, body=body, parent_id=(parent.id if parent else None))
        # created_at 필드가 자동 default가 아니면 주석 해제:
        # from datetime import datetime
        # doc.created_at = datetime.utcnow()

        session.add(doc)
        session.commit()
        flash("문서를 생성했습니다.", "success")
        return redirect(url_for("view_document", doc_id=doc.id) if "view_document" in current_app.view_functions else url_for("index"))

    # GET
    try:
        all_docs = Document.query.order_by(Document.created_at.desc()).all()
    except Exception:
        all_docs = Document.query.all()
    return render_template("patch/create_document_extra.html", all_docs=all_docs)


@patch_bp.route("/document/<int:doc_id>/delete", methods=["POST"])
def delete_document(doc_id):
    """문서 삭제 (POST만 허용)."""
    if not _is_logged_in():
        abort(403)

    Document = _Document()
    if Document is None:
        abort(500)
    session, db = _db_sess()
    if session is None:
        abort(500)

    doc = session.get(Document, doc_id)
    if not doc:
        abort(404)

    # 시스템 문서 보호 (있다면)
    if getattr(doc, "is_system", False):
        flash("시스템 문서는 삭제할 수 없습니다.", "error")
        return redirect(url_for("index"))

    session.delete(doc)
    session.commit()
    flash("문서를 삭제했습니다.", "success")
    return redirect(url_for("index"))


@patch_bp.route("/logs")
def logs():
    """최근 로그 보기 (관리자만)."""
    if not _is_admin():
        abort(403)
    log_path = os.environ.get("APP_LOG_PATH", "app.log")
    lines = []
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        lines = [f"(로그 파일을 열 수 없습니다: {e})"]
    tail = "".join(lines[-500:])
    return render_template("patch/logs.html", tail=tail, log_path=log_path)


@patch_bp.route("/account/delete", methods=["GET","POST"])
def account_delete():
    """회원 탈퇴 (비밀번호 확인은 원 앱 로그인/해시 로직에 맞춰 수정 가능)."""
    if not _is_logged_in():
        abort(403)

    User = _User()
    session, db = _db_sess()
    if session is None or User is None:
        abort(500)

    u = _user()
    if request.method == "POST":
        confirm = request.form.get("confirm","").strip()
        if confirm != "DELETE":
            flash("확인 문구가 일치하지 않습니다. (DELETE)", "error")
            return redirect(request.url)

        # TODO: 필요시 사용자 소유 문서 처리(이관/익명화)
        session.delete(u)
        session.commit()
        flash("회원 탈퇴가 완료되었습니다.", "success")
        return redirect(url_for("index"))
    return render_template("patch/account_delete.html")
