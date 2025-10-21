# Byeollae Wiki — Minimal Backend Patch (No UI change)

이 패치는 **디자인/템플릿을 건드리지 않고**, 다음 오류만 해결합니다.
- `NameError: _log_action` (정의 누락)
- `/logs` 접속 시 `UndefinedColumn audit_log.user_email` 500 에러
- 문서 생성/삭제 시 감사 로그 누락

## 포함물
- `migrations/20251021_add_audit_log.sql` : PostgreSQL 스키마 보강 (idempotent)
- `templates/logs.html` : 로그 보기 템플릿 (기존 `_base.html` 상속)
- `tools/patch_apply.py` : `app.py`에 유틸과 /logs뷰를 주입(중복 실행해도 안전)

## 적용 순서
1) **스키마 반영** — Render DB 콘솔이나 psql에서 아래 스크립트 실행
   - `migrations/20251021_add_audit_log.sql`

2) **파일 추가 & 커밋** — 이 zip의 파일들을 레포 최상단에 그대로 추가/커밋
   - 기존 CSS/템플릿/레이아웃은 **변경 없음**

3) **패치 실행(로컬)** — 아래 명령으로 `app.py`에 최소 코드 삽입
   ```bash
   python tools/patch_apply.py
   git add app.py templates/logs.html tools/patch_apply.py migrations/20251021_add_audit_log.sql README_PATCH.md
   git commit -m "fix: add minimal audit log + /logs view (no UI change)"
   git push
   ```

> 주의: 본 패치는 문서 만들기/삭제/로그보기 로직만 보강합니다. 상/하단 배너, 버튼 위치 등 **UI는 기존 그대로 유지**됩니다.