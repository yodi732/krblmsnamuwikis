document.addEventListener("DOMContentLoaded", loadDocs);

const supabaseUrl = 'https://ytsavkksdgpvojovpoeh.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0c2F2a2tzZGdwdm9qb3Zwb2VoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ0MDg5NzEsImV4cCI6MjA3OTk4NDk3MX0.CHjdicKMkWROVmAt86Mjaq7qmD6nuxU-em-_HTVIFwE';
const supabaseClient = supabase.createClient(supabaseUrl, supabaseKey);

async function loadDocs() {
    const listDiv = document.getElementById("doc-list");
    const tocDiv = document.getElementById("toc");

    listDiv.innerHTML = "문서를 불러오는 중...";
    tocDiv.innerHTML = "문서를 불러오는 중...";

    const { data, error } = await supabaseClient
        .from("document")
        .select("*")
        .order("id", { ascending: false });

    if (error) {
        listDiv.innerHTML = "불러오기 실패";
        tocDiv.innerHTML = "불러오기 실패";
        return;
    }

    // 문서 목록
    listDiv.innerHTML = "";
    data.forEach(doc => {
        const a = document.createElement("a");
        a.href = `/document.html?id=${doc.id}`;
        a.textContent = doc.title;
        listDiv.appendChild(a);
        listDiv.appendChild(document.createElement("br"));
    });

    // 목차
    tocDiv.innerHTML = "";
    data.filter(d => d.parent_id == null).forEach(doc => {
        const a = document.createElement("a");
        a.href = `/document.html?id=${doc.id}`;
        a.textContent = doc.title;
        tocDiv.appendChild(a);
        tocDiv.appendChild(document.createElement("br"));
    });
}
