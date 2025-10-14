// Global confirm hooks for destructive actions
(function(){
  function wire(selector, messageBuilder){
    document.addEventListener('click', function(e){
      const btn = e.target.closest(selector);
      if(!btn) return;
      const msg = typeof messageBuilder === 'function' ? messageBuilder(btn) : messageBuilder;
      if(!confirm(msg)){ e.preventDefault(); e.stopPropagation(); }
    });
  }

  // Delete document
  wire('.confirm-delete', btn => {
    const title = btn.getAttribute('data-title') || '이 문서';
    return `정말로 '${title}'을(를) 삭제할까요? 이 작업은 되돌릴 수 없습니다.`;
  });

  // Logout
  wire('.confirm-logout', `로그아웃하시겠습니까?`);

  // Withdraw (account deletion)
  wire('.confirm-withdraw', `정말로 회원탈퇴하시겠습니까? 계정과 관련 데이터가 삭제됩니다.`);
})();
