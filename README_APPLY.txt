
별내위키 — 이용약관/개인정보처리방침 패치 번들
==========================================

이 압축파일에는 다음이 들어있습니다.
- templates/legal_terms.html           → 약관 단독 페이지 (교체/추가)
- templates/legal_privacy.html         → 개인정보처리방침 단독 페이지 (교체/추가)
- fragments/signup_terms_block.html    → 회원가입 아코디언에 붙여넣을 '약관 전문' HTML
- fragments/signup_privacy_block.html  → 회원가입 아코디언에 붙여넣을 '개인정보처리방침 전문' HTML
- static/css/policy.css                → 약관/정책 페이지 가독성 CSS (선택)

적용 방법
1) 레포에서 위 경로에 파일을 그대로 복사합니다.
   - 'templates' 폴더와 'static/css' 폴더 구조를 유지하세요.

2) 회원가입(templates/signup.html) 파일에서
   - "여기에 서비스 이용약관 전문을 넣으세요..." 문구가 있는 곳 → fragments/signup_terms_block.html 내용으로 교체
   - "여기에 개인정보처리방침 전문을 넣으세요..." 문구가 있는 곳 → fragments/signup_privacy_block.html 내용으로 교체

3) 단독 페이지 라우팅이 이미 연결되어 있다면 그대로 동작합니다.
   - /legal/terms  → legal_terms.html
   - /legal/privacy → legal_privacy.html

4) 문서 생성에서 하위 문서 선택 드롭다운에 상위문서만 보이게 하려면(미적용 시):
   app.py 예시
   --------------------------------------------------
   def _parent_choices():
       return Document.query.filter_by(is_system=False, parent_id=None)                .order_by(Document.created_at.desc()).all()
   --------------------------------------------------

5) 기본 진입 시 홈이 보이도록(미적용 시):
   @app.route("/")
   def index():
       roots = Document.query.filter_by(parent_id=None, is_system=False)                .order_by(Document.created_at.desc()).all()
       latest = Document.query.filter_by(is_system=False)                .order_by(Document.created_at.desc()).limit(10).all()
       return render_template("home.html", roots=roots, latest=latest)

문의: lyhjs1115@gmail.com
