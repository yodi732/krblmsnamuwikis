
async function requireLogin(){
  const { data:{ user }} = await supabase.auth.getUser();
  return user;
}
async function updateLoginUI(){
  const { data:{ user }} = await supabase.auth.getUser();
  const btn=document.getElementById("login-btn");
  const mail=document.getElementById("user-mail");
  if(user){
    btn.innerText="로그아웃";
    mail.innerText=user.email;
  } else {
    btn.innerText="구글 로그인";
    mail.innerText="";
  }
}
async function toggleLogin(){
  const { data:{ user }} = await supabase.auth.getUser();
  if(user){
    await supabase.auth.signOut();
    location.reload();
  } else {
    await supabase.auth.signInWithOAuth({provider:"google"});
  }
}
document.addEventListener("DOMContentLoaded",updateLoginUI);
