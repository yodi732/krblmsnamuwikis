📘 README.txt
별내위키 (Byeollae Wiki)
========================

개요
----
별내위키는 별내중학교 학생들이 함께 만드는 커뮤니티형 위키 사이트입니다.  
Flask + PostgreSQL 기반으로 제작되었으며, Render 플랫폼을 통해 배포됩니다.  

- 프로젝트 목적: 학교 커뮤니티와 학습 자료 공유
- 제작 언어: Python (Flask)
- 데이터베이스: PostgreSQL
- 배포 환경: Render
- 주요 기능:
  - 문서 생성 / 수정 / 삭제
  - 상위·하위 문서 구조
  - 사용자 회원가입, 로그인, 로그아웃, 탈퇴
  - 작성/수정 로그 보기
  - 이용약관 및 개인정보처리방침 문서
  - SEO(검색 노출)용 sitemap.xml, robots.txt 제공

폴더 구조
----------


/byeollae_wiki/
├── app.py # Flask 메인 실행 파일
├── models.py # 데이터베이스 모델 정의
├── templates/ # HTML 템플릿 (Jinja2)
│ ├── base.html
│ ├── home.html
│ ├── document_view.html
│ ├── create_document.html
│ ├── login.html
│ ├── register.html
│ ├── terms.html
│ └── privacy.html
├── static/
│ ├── style.css # 사이트 스타일시트
│ ├── logo.png
│ └── favicon.ico
├── sitemap.xml
├── robots.txt
├── requirements.txt
└── README.txt # (본 문서)


환경 변수
----------
Render 배포 시 다음 두 환경 변수를 설정해야 합니다.

| 환경 변수명   | 설명 |
|----------------|------|
| `DATABASE_URL` | PostgreSQL 연결 주소 |
| `SECRET_KEY`   | Flask 세션용 비밀 키 |

로컬 실행 방법
--------------
1. 의존성 설치  


pip install -r requirements.txt


2. Flask 서버 실행  


flask run


3. 브라우저 접속  


http://127.0.0.1:5000


배포 (Render)
-------------
1. GitHub에 전체 프로젝트 업로드  
2. Render → New Web Service → “Deploy from GitHub” 선택  
3. 환경 변수 설정 (`DATABASE_URL`, `SECRET_KEY`)  
4. `Build Command`: `pip install -r requirements.txt`  
5. `Start Command`: `gunicorn app:app`  

검색 노출(SEO)
---------------
- `/robots.txt` 와 `/sitemap.xml` 자동 제공
- 구글 Search Console 및 네이버 Search Advisor 등록 가능  
(HTML 인증 파일 업로드 후 `app.py` 라우트에 추가)

기타
----
- 사용자 비밀번호는 bcrypt로 해싱 저장되어 **평문으로 저장되지 않습니다**.
- 실전 서비스용으로 광고, 수익 활동은 포함되어 있지 않습니다.