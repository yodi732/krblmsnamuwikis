# 별내 위키 - 핫픽스 4

- 트랜잭션 중단(`InFailedSqlTransaction`) 회피: 각 마이그레이션 단계를 개별 트랜잭션으로 실행
- `user.pw_hash` / `document.content` 보강, `body` → `content` 이전(있는 경우만)
- 로그인 케이스 불일치 방지, UI 개선, 약관/개인정보 링크 동작
- 하위문서의 하위문서 생성 금지

## 로컬 실행(Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY="dev"
python .\app.py
```
