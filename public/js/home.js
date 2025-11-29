async function fetchDocs() {
  const res = await fetch('/.netlify/functions/docs');
  if (!res.ok) {
    console.error('문서 목록 불러오기 실패', await res.text());
    return [];
  }
  return await res.json();
}

function buildTree(docs) {
  const byId = new Map();
  const roots = [];

  docs.forEach(d => {
    d.children = [];
    byId.set(d.id, d);
  });

  docs.forEach(d => {
    if (d.parent_id) {
      const parent = byId.get(d.parent_id);
      if (parent) {
        parent.children.push(d);
      } else {
        roots.push(d);
      }
    } else {
      roots.push(d);
    }
  });

  return roots;
}

function renderToc(container, nodes, depth = 0) {
  if (!nodes.length) {
    container.innerHTML = '<p>문서가 없습니다.</p>';
    return;
  }

  const ul = document.createElement('ul');
  ul.style.marginLeft = (depth * 12) + 'px';

  nodes.forEach(node => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = '/document.html?id=' + encodeURIComponent(node.id);
    a.textContent = node.title;
    li.appendChild(a);

    if (node.children && node.children.length > 0) {
      renderToc(li, node.children, depth + 1);
    }

    ul.appendChild(li);
  });

  container.appendChild(ul);
}

function renderDocList(container, docs) {
  container.innerHTML = '';

  if (!docs.length) {
    container.innerHTML = '<li>문서가 없습니다.</li>';
    return;
  }

  const sorted = [...docs].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );

  sorted.forEach(d => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = '/document.html?id=' + encodeURIComponent(d.id);
    a.textContent = d.title;
    li.appendChild(a);

    if (d.created_at) {
      const small = document.createElement('small');
      const dt = new Date(d.created_at);
      small.textContent = ' ' + dt.toLocaleString('ko-KR');
      li.appendChild(small);
    }

    container.appendChild(li);
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  const tocRoot = document.getElementById('toc-root');
  const docList = document.getElementById('doc-list');

  try {
    const docs = await fetchDocs();
    const tree = buildTree(docs);
    tocRoot.innerHTML = '';
    renderToc(tocRoot, tree, 0);
    renderDocList(docList, docs);
  } catch (err) {
    console.error(err);
    tocRoot.innerHTML = '<p>문서를 불러오는 중 오류가 발생했습니다.</p>';
    docList.innerHTML = '<li>문서 목록을 불러오는 중 오류가 발생했습니다.</li>';
  }
});
