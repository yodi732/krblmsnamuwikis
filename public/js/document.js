async function fetchDoc(id) {
  const res = await fetch('/.netlify/functions/docs?id=' + encodeURIComponent(id));
  if (!res.ok) {
    throw new Error('문서 불러오기 실패: ' + (await res.text()));
  }
  return await res.json();
}

async function updateDoc(payload) {
  const res = await fetch('/.netlify/functions/docs', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error('문서 저장 실패: ' + (await res.text()));
  }
  return await res.json();
}

function getQueryParam(name) {
  const url = new URL(window.location.href);
  return url.searchParams.get(name);
}

document.addEventListener('DOMContentLoaded', async () => {
  const id = getQueryParam('id');
  if (!id) {
    alert('문서 ID가 없습니다.');
    return;
  }

  const titleEl = document.getElementById('doc-title');
  const metaEl = document.getElementById('doc-meta');
  const contentEl = document.getElementById('doc-content');
  const form = document.getElementById('edit-form');
  const editTitle = document.getElementById('edit-title');
  const editContent = document.getElementById('edit-content');

  try {
    const doc = await fetchDoc(id);
    titleEl.textContent = doc.title;
    metaEl.textContent = doc.created_at
      ? '작성일: ' + new Date(doc.created_at).toLocaleString('ko-KR')
      : '';
    contentEl.textContent = doc.content;

    editTitle.value = doc.title;
    editContent.value = doc.content;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        id: doc.id,
        title: editTitle.value.trim(),
        content: editContent.value,
        parent_id: doc.parent_id || null,
      };
      try {
        const updated = await updateDoc(payload);
        alert('저장되었습니다.');
        titleEl.textContent = updated.title;
        contentEl.textContent = updated.content;
      } catch (err) {
        console.error(err);
        alert('저장 중 오류가 발생했습니다.');
      }
    });

  const deleteBtn = document.getElementById('delete-btn');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', async () => {
      if (!confirm('정말 이 문서를 삭제하시겠습니까?')) return;
      try {
        const res = await fetch('/.netlify/functions/docs?id=' + encodeURIComponent(doc.id), {
          method: 'DELETE',
        });
        if (!res.ok && res.status !== 204) {
          throw new Error('삭제 실패: ' + (await res.text()));
        }
        alert('문서가 삭제되었습니다.');
        window.location.href = '/';
      } catch (err) {
        console.error(err);
        alert('문서 삭제 중 오류가 발생했습니다.');
      }
    });
  }

  } catch (err) {
    console.error(err);
    alert('문서를 불러오는 중 오류가 발생했습니다.');
  }
});
