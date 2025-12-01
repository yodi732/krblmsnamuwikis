const { Client } = require('pg');

const connectionString = process.env.PG_CONNECTION_STRING;

exports.handler = async (event, context) => {
  if (!connectionString) {
    return {
      statusCode: 500,
      body: 'PG_CONNECTION_STRING 환경 변수가 설정되지 않았습니다.',
    };
  }

  const client = new Client({ connectionString });

  try {
    await client.connect();
    const method = event.httpMethod;

    if (method === 'GET') {
      const params = event.queryStringParameters || {};
      const id = params.id;

      if (id) {
        const result = await client.query(
          'SELECT id, title, content, parent_id, created_at FROM document WHERE id = $1',
          [id]
        );
        if (result.rows.length === 0) {
          return { statusCode: 404, body: 'not found' };
        }
        return {
          statusCode: 200,
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
          body: JSON.stringify(result.rows[0]),
        };
      } else {
        const result = await client.query(
          'SELECT id, title, parent_id, created_at, content FROM document ORDER BY created_at ASC'
        );
        return {
          statusCode: 200,
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
          body: JSON.stringify(result.rows),
        };
      }
    }

    if (method === 'POST') {
      const body = JSON.parse(event.body || '{}');
      const { title, content, parent_id } = body;
      if (!title || !content) {
        return { statusCode: 400, body: 'title, content 필요' };
      }

      const result = await client.query(
        `INSERT INTO document (title, content, parent_id)
         VALUES ($1, $2, $3)
         RETURNING id, title, content, parent_id, created_at`,
        [title, content, parent_id || null]
      );

      return {
        statusCode: 201,
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify(result.rows[0]),
      };
    }

    if (method === 'PUT') {
      const body = JSON.parse(event.body || '{}');
      const { id, title, content, parent_id } = body;

      if (!id || !title || !content) {
        return { statusCode: 400, body: 'id, title, content 필요' };
      }

      const result = await client.query(
        `UPDATE document
           SET title = $1,
               content = $2,
               parent_id = $3
         WHERE id = $4
         RETURNING id, title, content, parent_id, created_at`,
        [title, content, parent_id || null, id]
      );

      if (result.rows.length === 0) {
        return { statusCode: 404, body: 'not found' };
      }

      return {
        statusCode: 200,
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify(result.rows[0]),
      };
    }

    if (method === 'DELETE') {
      const params = event.queryStringParameters || {};
      const id = params.id;
      if (!id) {
        return { statusCode: 400, body: 'id 필요' };
      }

      await client.query('DELETE FROM document WHERE id = $1', [id]);
      return { statusCode: 204, body: '' };
    }

    return { statusCode: 405, body: 'method not allowed' };
  } catch (err) {
    console.error(err);
    return { statusCode: 500, body: 'server error' };
  } finally {
    await client.end();
  }
};
