
import { supabase } from "./supabase.js";
async function loadDocs() {
    const list = document.getElementById("doc-list");
    list.innerHTML = "문서 불러오는 중...";
    const { data, error } = await supabase.from("document").select("*").order("created_at", { ascending: true });
    if (error) { list.innerHTML = "오류 발생"; return; }
    list.innerHTML = "";
    data.forEach(doc=>{
        const a=document.createElement("a");
        a.href = `/document.html?id=${doc.id}`;
        a.textContent = doc.title;
        list.appendChild(a);
        list.appendChild(document.createElement("br"));
    });
}
document.addEventListener("DOMContentLoaded", loadDocs);
