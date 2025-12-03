document.getElementById("save-btn").onclick=async()=>{
 const title=document.getElementById("title").value.trim();
 const content=document.getElementById("content").value.trim();
 if(!title||!content){alert("입력 필요");return;}
 const {data,error}=await supabase.from("document").insert([{title,content}]).select().single();
 if(error){alert("오류");return;}
 await supabase.from("activity_logs").insert([{email:(await supabase.auth.getUser()).data.user.email,action:"create",document_id:data.id}]);
 location.href="/document.html?id="+data.id;
};