\
document.addEventListener('click', function(e){
  const target = e.target.closest('form[data-confirm] button, form[data-confirm] input[type=submit]');
  if (target){
    const form = target.closest('form[data-confirm]');
    const msg = form.getAttribute('data-confirm') || '진행할까요?';
    if (!confirm(msg)){
      e.preventDefault();
    }
  }
});
