
function toggleReveal(btn){
  const input = btn.previousElementSibling;
  if (!input) return;
  if (input.type === "password"){
    input.type = "text"; btn.textContent = "숨김";
  } else {
    input.type = "password"; btn.textContent = "표시";
  }
}
// confirm on forms
document.addEventListener("submit", function(e){
  const form = e.target;
  const msg = form.getAttribute("data-confirm");
  if (msg && !confirm(msg)){
    e.preventDefault();
  }
}, true);
