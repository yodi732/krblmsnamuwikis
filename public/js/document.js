const id = new URLSearchParams(location.search).get("id");

async function load() {
  const { data, error } = await window.sb
    .from("document")
    .select("*")
    .eq("id", id)
    .single();

  if (error) return alert("문서 불러오기 실패");

  document.getElementById("title").value = data.title;
  document.getElementById("content").value = data.content;
}
load();

document.getElementById("save").onclick = async () => {
  const title = document.getElementById("title").value;
  const content = document.getElementById("content").value;

  await window.sb
    .from("document")
    .update({ title, content })
    .eq("id", id);

  location.reload();
};

document.getElementById("delete").onclick = async () => {
  await window.sb.from("document").delete().eq("id", id);
  location.href = `/index.html`;
};
