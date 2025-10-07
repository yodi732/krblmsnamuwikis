
# School Wiki (Flask + SQLite, Render-ready)

최소 기능의 위키(제목/내용 저장)입니다. Render에 바로 배포할 수 있게 구성했습니다.
- DB는 `instance/database.db`
- 앱 시작 시 `schema.sql` 자동 적용 (app.py의 `ensure_schema()`)
- Start Command에서도 `init_db.py`를 먼저 실행해 이중 안전장치

## 배포 (Render)
1. 이 폴더를 새 GitHub 레포지토리로 업로드
2. Render에서 New → Web Service → GitHub 레포 선택
3. 설정
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `bash -c "python init_db.py && gunicorn app:app --bind 0.0.0.0:$PORT"`
4. 배포 후 `/health`가 200이면 정상입니다.

## 로컬 실행
```bash
pip install -r requirements.txt
python init_db.py
python app.py
# 브라우저: http://localhost:5000
```
