// new.js
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById("saveBtn").addEventListener("click", createDocument);
});

const supabaseUrl = 'https://ytsavkksdgpvojovpoeh.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0c2F2a2tzZGdwdm9qb3Zwb2VoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ0MDg5NzEsImV4cCI6MjA3OTk4NDk3MX0.CHjdicKMkWROVmAt86Mjaq7qmD6nuxU-em-_HTVIFwE';
const supabaseClient = supabase.createClient(supabaseUrl, supabaseKey);

async function createDocument() {
    const title = document.getElementById("title").value.trim();
    const content = document.getElementById("content").value.trim();
    const parent = document.getElementById("parent")?.value || null;

    if (!title) {
        alert("제목을 입력하세요.");
        return;
    }

    const { data, error } = await supabaseClient
        .from('document')
        .insert([{ title, content, parent_id: parent ? Number(parent) : null }])
        .select();

    if (error) {
        alert("문서 생성 실패: " + error.message);
        return;
    }

    alert("문서가 생성되었습니다!");
    location.href = `/document.html?id=${data[0].id}`;
}