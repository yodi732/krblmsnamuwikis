
document.addEventListener("DOMContentLoaded", async ()=>{
  const user=await requireLogin();
  if(!user){ alert("로그인 필요"); location.href="/index.html"; }

  document.getElementById("create-btn").onclick=async()=>{
    const t=document.getElementById("new-title").value;
    const c=document.getElementById("new-content").value;
    let {data, error}=await supabase.from("document").insert({
      title:t, content:c
    }).select().single();
    await supabase.from("activity_logs").insert({
      user_email:user.email,
      action:"문서 생성: "+t,
      document_id:data.id
    });
    location.href="/document.html?id="+data.id;
  };
});
