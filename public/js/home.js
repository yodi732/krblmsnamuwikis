
document.addEventListener("DOMContentLoaded", async () => {
  const list=document.getElementById("doc-list");
  list.textContent="불러오는 중...";
  const {data,error}=await supabase.from("document").select("*").order("created_at",{ascending:true});
  if(error){list.textContent="오류";return;}
  list.innerHTML="";
  data.forEach(d=>{
    const a=document.createElement("a");
    a.href="/document.html?id="+d.id;
    a.textContent=d.title;
    list.appendChild(a);
    list.appendChild(document.createElement("br"));
  });
});
