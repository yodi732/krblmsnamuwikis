
from __future__ import annotations
import os, io, datetime
from typing import Optional

from flask import Blueprint, request, redirect, url_for, flash, render_template, g, current_app, abort
from werkzeug.exceptions import Forbidden

patch_bp = Blueprint("patch", __name__)

# ---------- Helpers ----------
def _is_logged_in() -> bool:
    # 지원: g.user 또는 flask_login.current_user
    if getattr(g, "user", None):
        return True
    try:
        from flask_login import current_user
        return bool(current_user.is_authenticated)
    except Exception:
        return False

def _current_email() -> str:
    # g.user.email 또는 flask_login.current_user.email 추정
    u = getattr(g, "user", None)
    if u and getattr(u, "email", None):
        return u.email
    try:
        from flask_login import current_user
        if current_user and getattr(current_user, "email", None):
            return current_user.email
    except Exception:
        pass
    return "anonymous"

def _audit_path() -> str:
    p = os.environ.get("APP_AUDIT_LOG")
    if p:
        return p
    # 앱 루트 기준
    root = current_app.root_path if current_app else os.getcwd()
    return os.path.join(root, "audit.log")

def write_audit(action: str, doc_id: Optional[int]=None, title: Optional[str]=None):
    # ISO UTC
    ts = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    line = f"{ts} | {_current_email()} | {action} | doc_id={doc_id} | title={title or ''}\n"
    try:
        with open(_audit_path(), "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        current_app.logger.error(f"[audit] write failed: {e}")

# ---------- Optional SQLAlchemy hooks ----------
def _try_attach_sa_hooks():
    try:
        # 프로젝트 구조에 맞춰 가져오기
        from app import db
        # Document 모델 흔한 이름 가정
        try:
            from app import Document
        except Exception:
            # 다른 파일에 있을 수 있음: models
            try:
                from models import Document  # type: ignore
            except Exception:
                Document = None

        if not db or not Document:
            return

        from sqlalchemy import event

        @event.listens_for(Document, "after_insert")
        def _after_insert(mapper, connection, target):
            try:
                write_audit("create", getattr(target, "id", None), getattr(target, "title", None))
            except Exception:
                pass

        @event.listens_for(Document, "after_update")
        def _after_update(mapper, connection, target):
            try:
                write_audit("update", getattr(target, "id", None), getattr(target, "title", None))
            except Exception:
                pass

        @event.listens_for(Document, "after_delete")
        def _after_delete(mapper, connection, target):
            try:
                # 삭제 후에는 title 접근 어려울 수 있어 보호
                write_audit("delete", getattr(target, "id", None), getattr(target, "title", None))
            except Exception:
                pass
    except Exception as e:
        try:
            current_app.logger.warning(f"[audit] SA hook attach skipped: {e}")
        except Exception:
            pass

@patch_bp.before_app_request
def _ensure_hooks():
    # 한번만 시도
    if not getattr(current_app, "_audit_hooks_attached", False):
        _try_attach_sa_hooks()
        current_app._audit_hooks_attached = True

# ---------- Routes ----------

@patch_bp.route("/logs")
def logs():
    # 로그인한 누구나
    if not _is_logged_in():
        abort(403)
    # 앱 실행 로그 + 감사 로그 모두 병합 표시 (최근 N줄)
    app_log = os.environ.get("APP_LOG_PATH") or os.path.join(current_app.root_path, "app.log")
    audit_log = _audit_path()
    def tail(path, lines=500):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.readlines()[-lines:]
        except Exception:
            return []
    merged = []
    merged += [f"[APP] {ln}" for ln in tail(app_log, 300)]
    merged += [f"[AUDIT] {ln}" for ln in tail(audit_log, 300)]
    # 최신순 정렬 시도: 앞부분 ISO/타임존 가정이 다를 수 있어 그대로 출력
    return render_template("patch/logs.html", lines=merged)

@patch_bp.route("/document/<int:doc_id>/delete", methods=["POST"])
def delete_document(doc_id: int):
    # 실제 삭제는 기존 앱의 삭제 로직에 위임하기 어렵기 때문에
    # 기존 앱의 삭제 엔드포인트가 있으면 그쪽으로 리디렉트,
    # 없으면 간단한 DB 삭제 훅 제공 (옵션).
    # 1) 우선 감사 로그
    write_audit("delete_request", doc_id, None)

    # 2) 기존 앱에 delete_document 함수가 있다면 호출
    try:
        from app import db
        try:
            from app import Document
        except Exception:
            from models import Document  # type: ignore
        doc = Document.query.get_or_404(doc_id)
        title = getattr(doc, "title", None)
        db.session.delete(doc)
        db.session.commit()
        write_audit("delete", doc_id, title)
        flash("문서를 삭제했습니다.", "success")
    except Exception as e:
        current_app.logger.error(f"[patch delete] fallback failed: {e}")
        flash("삭제 중 오류가 발생했습니다.", "error")
    return redirect(url_for("index"))

@patch_bp.route("/account/delete", methods=["GET", "POST"])
def account_delete():
    if not _is_logged_in():
        abort(403)
    if request.method == "GET":
        return render_template("patch/account_delete.html")
    # POST
    code = request.form.get("confirm", "")
    if code != "DELETE":
        flash("확인 문구가 일치하지 않습니다. 'DELETE'를 입력하세요.", "warning")
        return redirect(url_for("patch.account_delete"))
    # 실제 프로젝트에 맞게 사용자 삭제/비활성화
    try:
        # flask_login 사용시:
        try:
            from flask_login import current_user, logout_user
            u = current_user
            email = getattr(u, "email", None)
            # 실제 삭제/비활성화는 프로젝트 정책에 맞게 구현
            logout_user()
            write_audit("account_delete", None, f"user={email}")
        except Exception:
            write_audit("account_delete", None, f"user={_current_email()}")
    except Exception as e:
        current_app.logger.error(f"[patch account_delete] {e}")
    flash("회원탈퇴 처리되었습니다.", "success")
    return redirect(url_for("index"))

# simple view for logs template (inline minimal)
@patch_bp.app_template_global()
def patch_now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat()+"Z"
