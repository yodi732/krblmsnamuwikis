document.addEventListener("DOMContentLoaded",async()=>{
 const box=document.getElementById("logs");
 const {data,error}=await supabase.from("activity_logs").select("*").order("created_at",{ascending:false});
 if(error){box.textContent="오류";return;}
 box.innerHTML="";
 data.forEach(l=>{
   const div=document.createElement("div");
   div.textContent=`${l.email} | ${l.action} | ${l.document_id} | ${l.created_at}`;
   box.appendChild(div);
 });
});