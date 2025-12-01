// logs.js
document.addEventListener('DOMContentLoaded', loadLogs);

const supabaseUrl = 'https://ytsavkksdgpvojovpoeh.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0c2F2a2tzZGdwdm9qb3Zwb2VoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ0MDg5NzEsImV4cCI6MjA3OTk4NDk3MX0.CHjdicKMkWROVmAt86Mjaq7qmD6nuxU-em-_HTVIFwE';
const supabaseClient = supabase.createClient(supabaseUrl, supabaseKey);

async function loadLogs() {
    const container = document.getElementById("logs");
    container.innerHTML = "불러오는 중...";

    const { data, error } = await supabaseClient
        .from('activity_logs')
        .select('*')
        .order('id', { ascending: false });

    if (error) {
        container.innerHTML = "로그를 불러올 수 없음";
        return;
    }

    container.innerHTML = "";

    data.forEach(row => {
        const div = document.createElement("div");
        div.textContent = `[${row.created_at}] ${row.email} - ${row.action}`;
        container.appendChild(div);
    });
}