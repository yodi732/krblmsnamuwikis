const { Client } = require("pg");
const { createClient } = require("@supabase/supabase-js");

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);

exports.handler = async (event) => {
  const client = new Client({ connectionString: process.env.PG_CONNECTION_STRING });
  await client.connect();

  const method = event.httpMethod;

  if (method === "POST") {
    const body = JSON.parse(event.body);
    const { title, content, email } = body;

    const result = await client.query(
      "INSERT INTO document (title, content) VALUES ($1, $2) RETURNING id",
      [title, content]
    );

    await supabase.from("activity_logs").insert({
      email,
      action:"create",
      doc_id: result.rows[0].id
    });

    return { statusCode:200, body:JSON.stringify({ id:result.rows[0].id }) };
  }

  if (method === "PUT") {
    const id = event.queryStringParameters.id;
    const { title, content, email } = JSON.parse(event.body);

    await client.query(
      "UPDATE document SET title=$1, content=$2 WHERE id=$3",
      [title, content, id]
    );

    await supabase.from("activity_logs").insert({
      email,
      action:"update",
      doc_id:id
    });

    return { statusCode:200, body:'"ok"' };
  }

  if (method === "DELETE") {
    const id = event.queryStringParameters.id;
    const email = event.queryStringParameters.email;

    await client.query("DELETE FROM document WHERE id=$1", [id]);

    await supabase.from("activity_logs").insert({
      email,
      action:"delete",
      doc_id:id
    });

    return { statusCode:200, body:'"deleted"' };
  }

  return { statusCode:400, body:"bad request" };
};