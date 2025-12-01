const SUPABASE_URL='https://ytsavkksdgpvojovpoeh.supabase.co';
const SUPABASE_ANON_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0c2F2a2tzZGdwdm9qb3Zwb2VoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ0MDg5NzEsImV4cCI6MjA3OTk4NDk3MX0.CHjdicKMkWROVmAt86Mjaq7qmD6nuxU-em-_HTVIFwE';
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';
const supabase=createClient(SUPABASE_URL,SUPABASE_ANON_KEY);

document.addEventListener("DOMContentLoaded", async ()=>{
  const box=document.getElementById("logs")||document.body;
  const {data,error}=await supabase.from("activity_logs").select("*").order("id",{ascending:false});
  if(error){ box.innerHTML="ERR"; return;}
  box.innerHTML="";
  data.forEach(l=>{
    const div=document.createElement("div");
    div.textContent=`${l.created_at} | ${l.email} | ${l.action} | doc ${l.doc_id}`;
    box.appendChild(div);
  });
});
