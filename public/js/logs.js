
const supabase = window.supabase.createClient(
    window.SUPABASE_URL || '',
    window.SUPABASE_ANON_KEY || ''
);

async function loadLogs(){
    const cont = document.getElementById("log-container");

    const { data: { session } } = await supabase.auth.getSession();
    if(!session){
        cont.innerHTML = "로그인이 필요합니다.";
        return;
    }

    const { data, error } = await supabase
      .from("activity_logs")
      .select("*")
      .order("timestamp",{ascending:false});

    if(error){
        cont.innerHTML="오류 발생";
        return;
    }

    cont.innerHTML="";
    data.forEach(log=>{
        const d=document.createElement("div");
        d.style="padding:12px;border:1px solid #ddd;margin-bottom:10px;background:#fff;border-radius:6px;";
        d.innerHTML = `
            <div><b>이메일:</b> ${log.email}</div>
            <div><b>작업:</b> ${log.action}</div>
            <div><b>문서 ID:</b> ${log.doc_id}</div>
            <div><b>시간:</b> ${new Date(log.timestamp).toLocaleString("ko-KR")}</div>
        `;
        cont.appendChild(d);
    });
}
loadLogs();
