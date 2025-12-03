
import { supabase } from "./supabase.js";
async function loadLogs(){
    const box=document.getElementById("logs");
    box.innerHTML="불러오는 중...";
    const {data,error}=await supabase.from("activity_logs").select("*").order("created_at",{ascending:false});
    if(error){box.innerHTML="오류";return;}
    box.innerHTML="";
    data.forEach(log=>{
        const div=document.createElement("div");
        div.textContent=`${log.email} | ${log.action} | doc ${log.document_id} | ${log.created_at}`;
        box.appendChild(div);
    });
}
document.addEventListener("DOMContentLoaded",loadLogs);
