const { Client } = require("pg");
const { createClient } = require("@supabase/supabase-js");

exports.handler = async (event) => {
  // PostgreSQL 연결
  const client = new Client({
    connectionString: process.env.PG_CONNECTION_STRING,
  });

  await client.connect();

  const method = event.httpMethod;

  // Supabase (로그 저장 용)
  const supabase = createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_SERVICE_KEY
  );

  // ---------------------------------------------------
  // 📌 GET: 문서 목록 조회
  // ---------------------------------------------------
  if (method === "GET") {
    const result = await client.query(
      "SELECT id, title, content, parent_id, created_at FROM document ORDER BY id DESC"
    );
    await client.end();

    return {
      statusCode: 200,
      body: JSON.stringify(result.rows),
    };
  }

  // ---------------------------------------------------
  // 📌 POST: 문서 생성
  // ---------------------------------------------------
  if (method === "POST") {
    const body = JSON.parse(event.body);
    const { title, content, email } = body;

    const result = await client.query(
      "INSERT INTO document (title, content) VALUES ($1, $2) RETURNING id",
      [title, content]
    );

    await supabase.from("activity_logs").insert({
      email,
      action: "create",
      doc_id: result.rows[0].id,
    });

    await client.end();

    return {
      statusCode: 200,
      body: JSON.stringify({ id: result.rows[0].id }),
    };
  }

  // ---------------------------------------------------
  // 📌 PUT: 문서 수정
  // ---------------------------------------------------
  if (method === "PUT") {
    const id = event.queryStringParameters.id;
    const { title, content, email } = JSON.parse(event.body);

    await client.query(
      "UPDATE document SET title=$1, content=$2 WHERE id=$3",
      [title, content, id]
    );

    await supabase.from("activity_logs").insert({
      email,
      action: "update",
      doc_id: id,
    });

    await client.end();

    return {
      statusCode: 200,
      body: JSON.stringify("ok"),
    };
  }

  // ---------------------------------------------------
  // 📌 DELETE: 문서 삭제
  // ---------------------------------------------------
  if (method === "DELETE") {
    const id = event.queryStringParameters.id;
    const email = event.queryStringParameters.email;

    await client.query("DELETE FROM document WHERE id=$1", [id]);

    await supabase.from("activity_logs").insert({
      email,
      action: "delete",
      doc_id: id,
    });

    await client.end();

    return {
      statusCode: 200,
      body: JSON.stringify("deleted"),
    };
  }

  await client.end();

  return { statusCode: 400, body: "Bad Request" };
};