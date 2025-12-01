import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm'
const supabase=createClient('https://ytsavkksdgpvojovpoeh.supabase.co','eyJhbGciOiJIUzI...');
async function load(){const {data}=await supabase.from('krblmswiki').select('*').order('id',{ascending:false});const c=document.getElementById('docs');c.innerHTML=data.map(d=>`<a href="document.html?id=${d.id}">${d.title}</a>`).join('');}
load();