import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm'
const supabase=createClient('https://ytsavkksdgpvojovpoeh.supabase.co','eyJhbGciOiJIUzI...');
async function load(){const {data}=await supabase.from('activity_logs').select('*').order('id',{ascending:false});document.getElementById('logs').innerHTML=data.map(l=>`<div>${l.email} - ${l.action} - ${l.doc_id} - ${l.created_at}</div>`).join('');}
load();