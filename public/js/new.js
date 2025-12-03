
document.addEventListener("DOMContentLoaded",()=>{
 document.getElementById("save-btn").onclick=async()=>{
   const title=document.getElementById("title").value.trim();
   const content=document.getElementById("content").value.trim();
   if(!title||!content){alert("입력 필요");return;}
   const user=(await supabase.auth.getUser()).data.user;
   if(!user){alert("로그인이 필요합니다");return;}
   const {data,error}=await supabase.from("document").insert([{title,content}]).select().single();
   if(error){alert("오류");return;}
   await supabase.from("activity_logs").insert([{email:user.email,action:"create",document_id:data.id}]);
   location.href="/document.html?id="+data.id;
 };
});
