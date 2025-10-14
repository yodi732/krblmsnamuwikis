
⭐ StarWiki Render Hotfix (Drop‑in)

이 패키지는 기존 코드를 거의/전혀 수정하지 않고도 Render에서 발생한
- user.password 컬럼 없음
- document.created_by 컬럼 없음
- document.content 컬럼/스키마 불일치
- withdraw / create / view_document 엔드포인트 누락으로 인한 BuildError

를 자동으로 복구/회피하기 위한 **드롭인 부트스트랩**입니다.

────────────────────────────────────────────────────────

📦 구성
- autofix_bootstrap.py : 드롭인 모듈 (DB 자가치유 + 엔드포인트 스텁)

────────────────────────────────────────────────────────

🛠 적용 방법 (app.py 기준)

1) db 초기화 직후(= `db = SQLAlchemy(app)` 다음 줄), 어떤 쿼리/시드보다 먼저 아래를 추가:

    from autofix_bootstrap import init_autofix
    init_autofix(app, db)

2) 배포.
   - DATABASE_URL(=Render의 PostgreSQL) 또는 로컬/없으면 sqlite:///app.db로 동작
   - 이 모듈은 테이블이 없으면 만들고, 빠진 컬럼만 안전하게 추가합니다.
   - 또한 누락된 엔드포인트(stub)를 등록하여 템플릿의 url_for 에러를 차단합니다.

3) (선택) 실제 '문서 만들기' 페이지 등 실 서비스 엔드포인트가 준비되면
   - autofix가 등록한 스텁은 그대로 두어도 무해합니다.
   - 혹은 같은 경로로 진짜 라우트를 정의하면 Flask는 마지막 등록된 뷰를 사용하므로 대체됩니다.

────────────────────────────────────────────────────────

🔒 스키마 변경 내역
- user.password TEXT/VARCHAR(255) 추가 (없을 때만)
- document.content TEXT 추가 (없을 때만)
- document.created_by VARCHAR(255) 추가 (없을 때만)

데이터 파괴적 변경(드롭/리네임/타입변경)은 전혀 수행하지 않습니다.

────────────────────────────────────────────────────────

🐞 여전히 에러가 난다면?
- 템플릿이 'body' 또는 'author_email' 같은 과거 컬럼명을 참조하는지 확인
- 필요한 경우 컬럼을 추가로 선언해도 됩니다 (패턴 동일):
  - SQLite : ALTER TABLE <table> ADD COLUMN <col> <TYPE>
  - Postgres: ALTER TABLE <table> ADD COLUMN IF NOT EXISTS <col> <TYPE>

────────────────────────────────────────────────────────

안정성만 보강, 기능/디자인은 그대로 유지합니다.
