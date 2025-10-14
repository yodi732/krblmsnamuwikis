
document.addEventListener("click", (e) => {
  // Confirm delete / logout / withdraw
  const btn = e.target.closest("[data-confirm]");
  if (btn) {
    const msg = btn.getAttribute("data-confirm") || "진행하시겠어요?";
    if (!confirm(msg)) {
      e.preventDefault();
      e.stopPropagation();
    }
  }
  if (e.target.matches("button.toggle[data-toggle='pw']")) {
    const input = e.target.closest(".row").querySelector("input[type='password'],input[type='text']");
    if (input) {
      if (input.type === "password") { input.type = "text"; e.target.textContent="숨김"; }
      else { input.type = "password"; e.target.textContent="표시"; }
    }
  }
});
