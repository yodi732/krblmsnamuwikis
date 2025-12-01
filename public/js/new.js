async function createDoc(payload) {
  const res = await fetch('/.netlify/functions/docs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error('문서 생성 실패: ' + (await res.text()));
  }
  return await res.json();
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('new-form');
  const titleInput = document.getElementById('title');
  const parentInput = document.getElementById('parent-id');
  const contentInput = document.getElementById('content');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const title = titleInput.value.trim();
    const parentRaw = parentInput.value.trim();
    const content = contentInput.value;

    if (!title || !content) {
      alert('제목과 내용을 모두 입력해주세요.');
      return;
    }

    const session = await supabaseClient.auth.getSession();
    const email = session.data.session?.user?.email || null;

    const payload = {
      email,
    
      title,
      content,
      parent_id: parentRaw ? Number(parentRaw) : null,
    };

    try {
      const created = await createDoc(payload);
      // 기록 저장
      await supabaseClient.from("activity_logs").insert({
          email: payload.email,
          action: "create",
          doc_id: created.id
      });
      alert('문서가 생성되었습니다.');
      window.location.href = '/document.html?id=' + encodeURIComponent(created.id);
    } catch (err) {
      console.error(err);
      alert('문서 생성 중 오류가 발생했습니다.');
    }
  });
});
