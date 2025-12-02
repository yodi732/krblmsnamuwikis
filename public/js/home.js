// home.js supabase direct version
import { supabase } from "./js/supabase.js";
import { updateLoginUI } from "./js/auth.js";

document.addEventListener("DOMContentLoaded", async () => {
  updateLoginUI();

  const container = document.getElementById("doc-list");
  const tocRoot = document.getElementById("toc-root");

  const { data, error } = await supabase
    .from("document")
    .select("*")
    .order("created_at", { ascending: true });

  if (error) {
    container.innerHTML = "<p>문서 목록을 불러올 수 없습니다.</p>";
    return;
  }

  function buildTree(docs) {
    const byId = new Map();
    const roots = [];
    docs.forEach(d => { d.children = []; byId.set(d.id, d); });
    docs.forEach(d => {
      if (d.parent_id && byId.has(d.parent_id)) {
        byId.get(d.parent_id).children.push(d);
      } else {
        roots.push(d);
      }
    });
    return roots;
  }

  function renderToc(parent, nodes, depth) {
    nodes.forEach(n => {
      const item = document.createElement("div");
      item.style.marginLeft = depth * 12 + "px";
      item.innerHTML = `<a href="document.html?id=${n.id}">${n.title}</a>`;
      parent.appendChild(item);
      if (n.children.length) renderToc(parent, n.children, depth + 1);
    });
  }

  const tree = buildTree(data);
  tocRoot.innerHTML = "";
  renderToc(tocRoot, tree, 0);

  container.innerHTML = data
    .map(d => `<li><a href="document.html?id=${d.id}">${d.title}</a></li>`)
    .join("");
});
