# 별내위키 (Portable)

## 실행
```
pip install -r requirements.txt
python app.py
```
- 기본 DB는 SQLite(`byeollae.db`).
- `DATABASE_URL`을 주면 PostgreSQL에 자동 연결됩니다. (`postgres://` 접두사는 자동 변환)

## 기능
- 회원가입(체크박스 필수: 이용약관/개인정보처리방침)
- 로그인/로그아웃, 회원탈퇴(확인창)
- 문서 만들기/보기, 하위문서 표시
- 시스템 문서(약관/정책) 자동 시드 (ORM 사용, 충돌 오류 없음)
