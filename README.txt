별내위키 - 최소 패치 (디자인 유지)

1) 이 압축의 templates/ 파일들을 기존 프로젝트의 templates/에 덮어쓰기(추가)하세요.
   - base.html은 건드리지 않습니다. 다만 푸터에 회원탈퇴 링크를 원하면 다음 한 줄만 직접 추가하세요:
     · <a href="{{ url_for('account_delete') }}">회원 탈퇴</a>

2) app.py 측에서 다음이 필요합니다.
   - /home 뷰에서 render_template('home.html', roots=roots, doc_model=Document) 처럼 doc_model=Document 전달
   - /logs, /account/delete 라우트는 이미 구현되어 있어야 합니다(기능 유지).
   - 삭제 라우트는 @app.post('/document/<int:doc_id>/delete') 형태(이미 적용되어 있으면 OK).

3) 디자인은 기존 CSS/구조를 그대로 사용합니다.
