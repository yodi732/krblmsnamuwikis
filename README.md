# Namuwiki-like Flask Wiki (교육용 데모) - Final

구성:
- /w/<title> : 문서 보기 (없는 문서면 편집으로 유도)
- /edit/<title> : 편집/생성 (제목 변경 가능, 충돌 검사)
- /delete/<title> : POST로 삭제 (홈으로 리다이렉트)
- 제목 기반 URL 사용 (인코딩 처리) - 공백, 특수문자 주의

실행:
$ python3 -m venv venv
$ source venv/bin/activate
$ pip install -r requirements.txt
$ python app.py
