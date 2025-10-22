# DB Hotfix Pack — Render quick fix

**목표**  
Render에서 발생한 다음 에러들을 즉시 해결합니다.

- `audit_log.doc_title` 컬럼 없음 → 500
- `"user".pw` 컬럼 없음 → 500
- (옵션) `document.is_legal` 컬럼 없음 → 읽기전용 문서 구분 실패

## 포함 파일
- `db_bootstrap.py` : 앱 시작 시 자동으로 필요한 컬럼을 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`로 보정합니다.
- `README.md` : 적용 방법

## 적용 방법 (아주 간단)
1) 이 폴더(또는 ZIP) 내용을 **프로젝트 루트**에 그대로 복사합니다.  
2) `app.py`(또는 Flask 앱이 초기화되는 파일)의 **아주 위쪽**에 아래 3줄을 추가하세요.

```python
# ==== DB Hotfix (must be placed before any model query) ====
from db_bootstrap import apply_hotfixes
apply_hotfixes()
# ===========================================================
```

> 만약 `wsgi.py`에서 앱을 생성한다면, **앱 생성 직후** 동일하게 위 3줄을 넣어 주세요.
> SQLAlchemy 인스턴스(`db`)가 전역에 없다면, 환경변수 `DATABASE_URL`을 사용해 psycopg로 직접 접속하여 수정합니다.

3) Render에 푸시하여 재배포하면, **첫 부팅 시 자동으로 컬럼 보정**이 수행됩니다.  
   (보정 쿼리는 안전한 `ADD COLUMN IF NOT EXISTS`만 사용합니다.)

## 내부 동작
- `ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS doc_title VARCHAR(255);`
- `ALTER TABLE "user"    ADD COLUMN IF NOT EXISTS pw        VARCHAR(255);`
- `ALTER TABLE document  ADD COLUMN IF NOT EXISTS is_legal  BOOLEAN DEFAULT FALSE;`

> 컬럼이 이미 존재하면 아무 일도 하지 않습니다.

## 참고
- 위 핫픽스는 **스키마 보정만** 수행합니다. 앱 로직에서 `User.pw`, `AuditLog.doc_title`, `Document.is_legal`
  필드를 사용 중이라면 정상 동작하게 됩니다.
- 추가로 필요한 마이그레이션이 있으면 같은 방식으로 쿼리를 추가해도 됩니다.
