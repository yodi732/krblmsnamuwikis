import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm';

const supabase = createClient(
  'https://ytsavkksdgpvojovpoeh.supabase.co',
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0c2F2a2tzZGdwdm9qb3Zwb2VoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ0MDg5NzEsImV4cCI6MjA3OTk4NDk3MX0.CHjdicKMkWROVmAt86Mjaq7qmD6nuxU-em-_HTVIFwE'
);

const id = new URLSearchParams(location.search).get("id");

async function load() {
  const { data } = await supabase
      .from("document")
      .select("*")
      .eq("id", id)
      .single();

  document.getElementById("title").value = data.title;
  document.getElementById("content").value = data.content;
}

load();

document.getElementById("save").onclick = async () => {
  const title = document.getElementById("title").value;
  const content = document.getElementById("content").value;

  await supabase
      .from("document")
      .update({ title, content })
      .eq("id", id);

  location.reload();
};

document.getElementById("delete").onclick = async () => {
  await supabase
      .from("document")
      .delete()
      .eq("id", id);

  location.href = "index.html";
};