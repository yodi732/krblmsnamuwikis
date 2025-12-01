const SUPABASE_URL='https://ytsavkksdgpvojovpoeh.supabase.co';
const SUPABASE_ANON_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0c2F2a2tzZGdwdm9qb3Zwb2VoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ0MDg5NzEsImV4cCI6MjA3OTk4NDk3MX0.CHjdicKMkWROVmAt86Mjaq7qmD6nuxU-em-_HTVIFwE';
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';
const supabase=createClient(SUPABASE_URL,SUPABASE_ANON_KEY);

document.addEventListener("DOMContentLoaded",()=>{
  const btn=document.getElementById("save-btn");
  if(!btn) return;
  btn.onclick=async ()=>{
    const title=document.getElementById("title").value;
    const content=document.getElementById("content").value;
    const pid_raw=document.getElementById("parent_id").value;
    const parent_id=pid_raw?Number(pid_raw):null;
    const {data,error}=await supabase.from("document").insert({title,content,parent_id,is_system:false}).select().single();
    if(error){ alert(error.message); return;}
    await supabase.from("activity_logs").insert({email:"unknown",action:"create",doc_id:data.id});
    location.href=`document.html?id=${data.id}`;
  };
});
