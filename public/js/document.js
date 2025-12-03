
import { supabase } from "./supabase.js";

const params=new URL(location.href).searchParams;
const id=params.get("id");

async function loadDoc(){
    const {data,error}=await supabase.from("document").select("*").eq("id",id).single();
    if(error){ alert("문서 오류"); return;}
    document.getElementById("title").value=data.title;
    document.getElementById("content").value=data.content;
}
async function saveDoc(){
    const title=document.getElementById("title").value.trim();
    const content=document.getElementById("content").value.trim();
    await supabase.from("document").update({title,content}).eq("id",id);
    await supabase.from("activity_logs").insert([{email:(await supabase.auth.getUser()).data.user.email, action:"update", document_id:id}]);
    alert("저장됨");
}
async function deleteDoc(){
    await supabase.from("document").delete().eq("id",id);
    await supabase.from("activity_logs").insert([{email:(await supabase.auth.getUser()).data.user.email, action:"delete", document_id:id}]);
    location.href="/index.html";
}
document.getElementById("save-btn").onclick=saveDoc;
document.getElementById("delete-btn").onclick=deleteDoc;
document.addEventListener("DOMContentLoaded", loadDoc);
