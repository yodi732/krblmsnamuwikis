Byeollae-Wiki DB Hotfix
=======================

문제
----
Render 로그의 에러:
  psycopg.errors.InvalidColumnReference: there is no unique or exclusion constraint matching the ON CONFLICT specification
원인: document.title 컬럼에 유니크(또는 배타) 제약이 없어 `ON CONFLICT (title)`가 동작하지 않음.

해결
----
아래 SQL을 데이터베이스에 한 번만 실행해서 유니크 인덱스를 추가하세요.

실행 방법(택1)
1) Render > PostgreSQL > psql 접속 > 아래 파일 내용 실행
2) 로컬 psql:
   psql "$DATABASE_URL" -f db_hotfix.sql

실행 후 애플리케이션을 재시작(Re-deploy)하면 됩니다.

권장 추가
--------
유저 이메일에도 유니크 인덱스를 추가합니다(중복 가입 방지).

포함 파일
---------
- db_hotfix.sql  : 유니크 인덱스 생성 스크립트
- README.txt     : 사용법
