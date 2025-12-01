const SUPABASE_URL='https://ytsavkksdgpvojovpoeh.supabase.co';
const SUPABASE_ANON_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0c2F2a2tzZGdwdm9qb3Zwb2VoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ0MDg5NzEsImV4cCI6MjA3OTk4NDk3MX0.CHjdicKMkWROVmAt86Mjaq7qmD6nuxU-em-_HTVIFwE';
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';
const supabase=createClient(SUPABASE_URL,SUPABASE_ANON_KEY);

async function load(){
  const params=new URLSearchParams(location.search);
  const id=Number(params.get("id"));
  const {data,error}=await supabase.from("document").select("*").eq("id",id).single();
  if(error){alert("error");return;}
  document.getElementById("title").value=data.title;
  document.getElementById("content").value=data.content;
  document.getElementById("parent_id").value=data.parent_id||"";
}
document.addEventListener("DOMContentLoaded",()=>{
  load();
  document.getElementById("update-btn").onclick=async ()=>{
    const params=new URLSearchParams(location.search);
    const id=Number(params.get("id"));
    const title=document.getElementById("title").value;
    const content=document.getElementById("content").value;
    const parent_id_raw=document.getElementById("parent_id").value;
    const parent_id=parent_id_raw?Number(parent_id_raw):null;
    await supabase.from("document").update({title,content,parent_id}).eq("id",id);
    await supabase.from("activity_logs").insert({email:"unknown",action:"update",doc_id:id});
    alert("updated");
  };
  document.getElementById("delete-btn").onclick=async ()=>{
    const params=new URLSearchParams(location.search);
    const id=Number(params.get("id"));
    await supabase.from("document").delete().eq("id",id);
    await supabase.from("activity_logs").insert({email:"unknown",action:"delete",doc_id:id});
    location.href="index.html";
  };
});
