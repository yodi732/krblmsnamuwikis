document.addEventListener('DOMContentLoaded', () => {
  // 일반 링크용 confirm
  document.querySelectorAll('a.js-confirm').forEach(a => {
    a.addEventListener('click', (e) => {
      const q = a.dataset.question || '이 작업을 진행할까요?';
      if (!confirm(q)) {
        e.preventDefault();
      }
    });
  });

  // form 제출 확인
  document.querySelectorAll('form.js-confirm-submit').forEach(f => {
    f.addEventListener('submit', (e) => {
      const q = f.dataset.question || '이 작업을 진행할까요?';
      if (!confirm(q)) {
        e.preventDefault();
      }
    });
  });

  // 비밀번호 표시 토글
  document.querySelectorAll('.js-toggle-password').forEach(btn => {
    btn.addEventListener('click', () => {
      const sel = btn.getAttribute('data-target');
      const input = document.querySelector(sel);
      if (input) {
        input.type = input.type === 'password' ? 'text' : 'password';
        btn.textContent = input.type === 'password' ? '표시' : '숨김';
      }
    });
  });
});
