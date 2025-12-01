
document.addEventListener("DOMContentLoaded", async ()=>{
  const user=await requireLogin();
  if(!user){ alert("로그인 필요"); location.href="/index.html"; }

  const box=document.getElementById("log-box");
  let {data, error}=await supabase.from("activity_logs").select("*").order("created_at",{ascending:false});
  if(error){ box.innerText="로드 오류"; return;}
  box.innerText="";
  data.forEach(l=>{
    const div=document.createElement("div");
    div.innerText=`${l.created_at} / ${l.user_email} / ${l.action}`;
    box.appendChild(div);
  });
});
