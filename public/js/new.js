
import { supabase } from "./supabase.js";
async function createDoc(){
    const title=document.getElementById("title").value.trim();
    const content=document.getElementById("content").value.trim();
    if(!title||!content){ alert("제목과 내용을 입력하세요"); return; }
    const { data, error } = await supabase.from("document").insert([{title,content}]).select().single();
    if(error){ console.error(error); alert("오류 발생"); return; }
    await supabase.from("activity_logs").insert([{email:(await supabase.auth.getUser()).data.user.email, action:"create", document_id:data.id}]);
    location.href = `/document.html?id=${data.id}`;
}
document.getElementById("save-btn").onclick=createDoc;
