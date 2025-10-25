[별내위키 패치: 약관/정책 + 네비 버튼 가독성]
1) 아래 파일을 프로젝트에 추가/교체하세요.
   - templates/legal_terms.html
   - templates/legal_privacy.html
2) 상단 버튼 글씨가 하얗게 보이거나 버튼이 사각형으로만 보이면
   - static/style.css 맨 아래에 static/patch_nav.css 내용을 붙여넣거나,
   - base.html <head> 안에 다음을 추가하세요.
     <link rel="stylesheet" href="{{ url_for('static', filename='patch_nav.css') }}">
3) (선택) base.html 상단 네비 예시
   <div class="topbar">
     <div class="topbar-inner">
       <a class="brand" href="{{ url_for('index') }}">별내위키</a>
       <div>
         {% if g.user %}
           <a class="nav-pill" href="{{ url_for('home') }}">홈</a>
           <a class="nav-pill" href="{{ url_for('create_document') }}">문서 만들기</a>
           <a class="nav-pill" href="{{ url_for('logs') }}">로그 보기</a>
           <span class="nav-user">{{ g.user.email }}</span>
           <a class="nav-pill" href="{{ url_for('logout') }}">로그아웃</a>
         {% else %}
           <a class="nav-pill" href="{{ url_for('index') }}">홈</a>
           <a class="nav-pill" href="{{ url_for('login') }}">로그인</a>
           <a class="nav-pill" href="{{ url_for('signup') }}">회원가입</a>
         {% endif %}
       </div>
     </div>
   </div>
