document.getElementById("save").onclick = async () => {
  const title = document.getElementById("title").value;
  const content = document.getElementById("content").value;

  const { data, error } = await window.sb
    .from("document")
    .insert({ title, content })
    .select();

  if (error) return alert(error.message);

  location.href = `/document.html?id=${data[0].id}`;
};
