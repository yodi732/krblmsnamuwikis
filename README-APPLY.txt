# 별내위키 – 패치 번들

## 적용 방법
1. Render 대시보드에서 현재 리포지토리에 이 ZIP의 내용으로 덮어쓰기(또는 Git 푸시).
2. 환경변수 확인
   - `DATABASE_URL` : Render의 Postgres URL
   - `SECRET_KEY` : 임의의 긴 값
3. 배포 후 첫 요청에서 DB 자동 초기화 + `user.pw_hash` 컬럼이 없으면 자동 추가됩니다.
4. 라우트/템플릿 주요 변경
   - 템플릿은 `url_for('create')` 사용 (호환을 위해 `create_doc` 별칭도 추가)
   - 홈: 최근변경 제거, 상/하위 문서 통합 트리(한 단계만 표시)
   - 로그인 화면: 약관/정책 본문 제거
   - 회원가입 화면: 체크박스 레이블을 한 줄, 마침표 제거, 요약 상자 제공
   - 하위문서의 하위문서 생성 방지(백엔드 검증)
5. 스타일
   - 버튼 테두리 제거, 여백 증가, 카드/입력 정렬 개선, 트리 스타일 세련화

## 계정 삭제
- `/delete_account` POST로 즉시 삭제. 법정 보관이 요구되는 로그만 기간 보관.

## 개발 실행
```
pip install -r requirements.txt
export FLASK_ENV=development
python app.py
```
