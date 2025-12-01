const SUPABASE_URL='https://ytsavkksdgpvojovpoeh.supabase.co';
const SUPABASE_ANON_KEY='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0c2F2a2tzZGdwdm9qb3Zwb2VoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ0MDg5NzEsImV4cCI6MjA3OTk4NDk3MX0.CHjdicKMkWROVmAt86Mjaq7qmD6nuxU-em-_HTVIFwE';
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';
const supabase=createClient(SUPABASE_URL,SUPABASE_ANON_KEY);

document.addEventListener("DOMContentLoaded", async ()=>{
  const list=document.getElementById("doc-list");
  const {data,error}=await supabase.from("document").select("*").order("id",{ascending:false});
  if(error){ list.innerHTML="error"; return;}
  list.innerHTML="";
  data.forEach(d=>{
    const a=document.createElement("a");
    a.href=`document.html?id=${d.id}`;
    a.textContent=d.title;
    list.appendChild(a);
    list.appendChild(document.createElement("br"));
  });
});
