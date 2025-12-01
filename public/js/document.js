// 문서 수정 및 삭제 + 로그 기록
async function saveDocument(id) {
  const { data: { session } } = await supabaseClient.auth.getSession();
  const email = session?.user?.email || null;

  const title = document.getElementById("title").value;
  const content = window.editor.getMarkdown();

  const res = await fetch(`/.netlify/functions/docs?id=${id}`, {
    method: "PUT",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ title, content, email })
  });

  const data = await res.json();
  if (data) {
    await supabaseClient.from("activity_logs").insert({
      email,
      action:"update",
      doc_id: id
    });
    alert("저장되었습니다.");
  }
}

async function deleteDocument(id) {
  const { data: { session } } = await supabaseClient.auth.getSession();
  const email = session?.user?.email || null;

  const res = await fetch(`/.netlify/functions/docs?id=${id}&email=${email}`, {
    method:"DELETE"
  });

  await supabaseClient.from("activity_logs").insert({
    email,
    action:"delete",
    doc_id:id
  });

  alert("문서가 삭제되었습니다.");
  location.href="/index.html";
}