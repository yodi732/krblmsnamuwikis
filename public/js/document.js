
document.addEventListener("DOMContentLoaded", async ()=>{
  const params=new URLSearchParams(location.search);
  const id=params.get("id");
  const title=document.getElementById("doc-title");
  const content=document.getElementById("doc-content");

  let {data, error}=await supabase.from("document").select("*").eq("id",id).single();
  if(error){ title.value="오류"; return;}
  title.value=data.title;
  content.value=data.content;

  const user=await requireLogin();
  if(!user){
    document.getElementById("save-btn").style.display="none";
    document.getElementById("del-btn").style.display="none";
  }

  document.getElementById("save-btn").onclick=async()=>{
    await supabase.from("document").update({
      title:title.value,
      content:content.value
    }).eq("id",id);
    await supabase.from("activity_logs").insert({
      user_email:user.email,
      action:"문서 수정: "+title.value,
      document_id:id
    });
    alert("저장되었습니다");
  };

  document.getElementById("del-btn").onclick=async()=>{
    await supabase.from("document").delete().eq("id",id);
    await supabase.from("activity_logs").insert({
      user_email:user.email,
      action:"문서 삭제: "+title.value,
      document_id:id
    });
    location.href="/index.html";
  };
});
