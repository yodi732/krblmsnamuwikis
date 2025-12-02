import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm';

const supabase = createClient(
  'https://ytsavkksdgpvojovpoeh.supabase.co',
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl0c2F2a2tzZGdwdm9qb3Zwb2VoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ0MDg5NzEsImV4cCI6MjA3OTk4NDk3MX0.CHjdicKMkWROVmAt86Mjaq7qmD6nuxU-em-_HTVIFwE'
);

document.getElementById("save").onclick = async () => {
  const title = document.getElementById("title").value;
  const content = document.getElementById("content").value;

  // 문서 저장
  const { data, error } = await supabase
      .from("document")
      .insert({ title, content })
      .select()
      .single();

  if (error) {
    alert(error.message);
    return;
  }

  // 사용자 이메일
  const { data: sessionData } = await supabase.auth.getUser();
  const email = sessionData?.user?.email || "unknown";

  // 로그 기록
  await supabase.from("activity_logs").insert({
    action: "create",
    doc_id: data.id,
    doc_title: title,
    email: email,
  });

  location.href = `document.html?id=${data.id}`;
};
