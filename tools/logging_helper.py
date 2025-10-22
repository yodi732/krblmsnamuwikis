def _log_action(user_email, action, doc_title, db=None, AuditLog=None):
    """안전한 로깅 헬퍼. db/AuditLog 를 전달하지 않아도 ImportError 방지.
       사용 예: _log_action(current_user().email, "create", doc.title, db=db, AuditLog=AuditLog)
       기존 코드에 인자 3개만 주입되어 있다면 조용히 no-op 처리합니다.
    """
    if db is None or AuditLog is None:
        return  # 안전하게 무시 (NameError 방지 목적)

    try:
        rec = AuditLog(user_email=user_email or "", action=action, doc_title=doc_title)
        db.session.add(rec)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
