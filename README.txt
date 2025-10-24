별내위키 — 덧씌우기(overlay) 패치

이 압축은 기존 템플릿을 바꾸지 않고, 기존 스타일을 유지한 채 필요한 조각만 추가합니다.

1) templates/ 폴더를 프로젝트의 templates/에 복사(덮어쓰기).
2) APP_PATCH_INSTRUCTIONS.txt대로 app.py 최소 변경 적용.
3) base.html 푸터에 회원탈퇴 링크 조건부 추가.

파란 상단 배너/로그인/회원가입/로그아웃 버튼 마크업은 기존 템플릿을 그대로 두고,
여기 제공된 _top_actions.html만 필요 화면에 include 하도록 했습니다.
