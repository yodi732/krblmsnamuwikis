-- 별내중위키 Netlify 버전에서 사용할 기본 document 테이블 정의
CREATE TABLE document (
  id         SERIAL PRIMARY KEY,
  title      TEXT NOT NULL,
  content    TEXT NOT NULL,
  is_system  BOOLEAN NOT NULL DEFAULT FALSE,
  parent_id  INTEGER REFERENCES document(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_document_parent ON document(parent_id);
