# 별내위키 (이메일 인증 제거 버전)

- Flask 3 / SQLAlchemy 2
- 이메일 인증 **없음**. @bl-m.kr 도메인만 가입 가능
- 상단 진한 파란 배너 + '로그 보기' 버튼
- 로그 페이지: 누가/언제/무슨 작업/대상/상세 표시
- 회원탈퇴 버튼은 로그인 후에만 노출

## 환경변수
- `DATABASE_URL` : Postgres 또는 SQLite (미설정 시 sqlite 파일 사용)
- `SECRET_KEY` : Flask 세션키

## 실행
pip install -r requirements.txt
gunicorn app:app --bind 0.0.0.0:8000
