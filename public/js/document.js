
document.addEventListener("DOMContentLoaded",async()=>{
 const id=new URLSearchParams(location.search).get("id");
 const {data,error}=await supabase.from("document").select("*").eq("id",id).single();
 if(error){alert("문서 없음");return;}
 document.getElementById("title").value=data.title;
 document.getElementById("content").value=data.content;

 document.getElementById("save-btn").onclick=async()=>{
   const t=document.getElementById("title").value.trim();
   const c=document.getElementById("content").value.trim();
   const user=(await supabase.auth.getUser()).data.user;
   await supabase.from("document").update({title:t,content:c}).eq("id",id);
   await supabase.from("activity_logs").insert([{email:user.email,action:"update",document_id:id}]);
   alert("저장됨");
 };

 document.getElementById("delete-btn").onclick=async()=>{
   const user=(await supabase.auth.getUser()).data.user;
   await supabase.from("document").delete().eq("id",id);
   await supabase.from("activity_logs").insert([{email:user.email,action:"delete",document_id:id}]);
   location.href="/index.html";
 };
});
