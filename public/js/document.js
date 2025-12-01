// document.js
document.addEventListener('DOMContentLoaded', loadDoc);

const supabaseUrl = 'https://ytsavkksdgpvojovpoeh.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0c2F2a2tzZGdwdm9qb3Zwb2VoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ0MDg5NzEsImV4cCI6MjA3OTk4NDk3MX0.CHjdicKMkWROVmAt86Mjaq7qmD6nuxU-em-_HTVIFwE';
const supabaseClient = supabase.createClient(supabaseUrl, supabaseKey);

async function loadDoc() {
    const params = new URLSearchParams(window.location.search);
    const id = params.get("id");

    if (!id) {
        alert("잘못된 문서 ID");
        return;
    }

    const { data, error } = await supabaseClient
        .from('document')
        .select('*')
        .eq('id', id)
        .single();

    if (error || !data) {
        alert("문서를 불러오지 못했습니다.");
        return;
    }

    document.getElementById("loading").style.display = "none";
    document.getElementById("title").value = data.title;
    document.getElementById("content").value = data.content;

    document.getElementById("saveBtn").onclick = () => saveDoc(id);
    document.getElementById("deleteBtn").onclick = () => deleteDoc(id);
}

async function saveDoc(id) {
    const title = document.getElementById("title").value.trim();
    const content = document.getElementById("content").value.trim();

    const { error } = await supabaseClient
        .from('document')
        .update({ title, content })
        .eq('id', id);

    if (error) {
        alert("저장 실패: " + error.message);
        return;
    }

    alert("저장되었습니다!");
}

async function deleteDoc(id) {
    if (!confirm("정말 삭제하시겠습니까?")) return;

    const { error } = await supabaseClient
        .from('document')
        .delete()
        .eq('id', id);

    if (error) {
        alert("삭제 실패: " + error.message);
        return;
    }

    alert("삭제되었습니다!");
    location.href = "/";
}