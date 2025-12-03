
document.addEventListener("DOMContentLoaded", async () => {
  const user = (await supabase.auth.getUser()).data.user;
  const loginBtn = document.querySelectorAll(".login-btn");
  const logoutBtn = document.querySelectorAll(".logout-btn");
  const protectedLinks = document.querySelectorAll(".need-login");

  if (user) {
    loginBtn.forEach(b=>b.style.display="none");
    logoutBtn.forEach(b=>b.style.display="inline-block");
    protectedLinks.forEach(b=>b.style.display="inline-block");
  } else {
    loginBtn.forEach(b=>b.style.display="inline-block");
    logoutBtn.forEach(b=>b.style.display="none");
    protectedLinks.forEach(b=>b.style.display="none");
  }
});

// Login
async function login() {
  await supabase.auth.signInWithOAuth({ provider:"google" });
}

// Logout
async function logout() {
  await supabase.auth.signOut();
  location.reload();
}
