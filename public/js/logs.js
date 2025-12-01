const supabase = window.supabase.createClient(
  window.SUPABASE_URL,
  window.SUPABASE_ANON_KEY
);

async function loadLogs() {
  const container = document.getElementById("log-container");

  const { data: { session } } = await supabase.auth.getSession();
  if (!session) {
    container.innerHTML = "로그인이 필요합니다.";
    return;
  }

  const { data, error } = await supabase
    .from("activity_logs")
    .select("*")
    .order("timestamp", { ascending: false });

  if (error) {
    container.innerHTML = "오류 발생: " + error.message;
    return;
  }

  if (!data || data.length === 0) {
    container.innerHTML = "아직 기록이 없습니다.";
    return;
  }

  container.innerHTML = "";
  data.forEach(log => {
    const div = document.createElement("div");
    div.className = "log-item";
    div.style = "padding:14px;background:#fff;border-radius:8px;box-shadow:0 3px 10px rgba(0,0,0,.04);margin-bottom:14px;";
    div.innerHTML = `
      <div><b>이메일:</b> ${log.email}</div>
      <div><b>작업:</b> ${log.action}</div>
      <div><b>문서 ID:</b> ${log.doc_id}</div>
      <div><b>시간:</b> ${new Date(log.timestamp).toLocaleString("ko-KR")}</div>
    `;
    container.appendChild(div);
  });
}
loadLogs();