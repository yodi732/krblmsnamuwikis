
document.addEventListener("DOMContentLoaded", async ()=>{
  const list=document.getElementById("doc-list");
  let { data, error } = await supabase.from("document").select("*").order("created_at",{ascending:true});  
  if(error){ list.innerHTML="로드 오류"; return;}
  list.innerHTML="";
  data.forEach(d=>{
    const a=document.createElement("a");
    a.href="/document.html?id="+d.id;
    a.innerText=d.title;
    list.appendChild(a);
    list.appendChild(document.createElement("br"));
  });
});
