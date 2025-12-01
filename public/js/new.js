// 문서 생성 + 로그 기록
async function createDocument() {
  const { data: { session } } = await supabaseClient.auth.getSession();
  const email = session?.user?.email || null;

  const title = document.getElementById("title").value;
  const content = window.editor.getMarkdown();

  const res = await fetch("/.netlify/functions/docs", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ title, content, email })
  });

  const data = await res.json();
  if (data && data.id) {
    await supabaseClient.from("activity_logs").insert({
      email,
      action:"create",
      doc_id: data.id
    });
    alert("문서가 생성되었습니다.");
    location.href = `/document.html?id=${data.id}`;
  } else {
    alert("문서 생성 실패");
  }
}