-- Use this SQL if your DB already has old tables and create_all() couldn't add columns.
BEGIN;
-- Users
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS password VARCHAR(255);
UPDATE "user" SET password = '' WHERE password IS NULL;
ALTER TABLE "user" ALTER COLUMN password SET NOT NULL;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS agreed_at TIMESTAMPTZ;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE INDEX IF NOT EXISTS idx_user_email ON "user"(email);

-- Documents
ALTER TABLE document ADD COLUMN IF NOT EXISTS author_id INTEGER;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_document_author') THEN
    ALTER TABLE document
      ADD CONSTRAINT fk_document_author FOREIGN KEY (author_id) REFERENCES "user"(id) ON DELETE SET NULL;
  END IF;
END$$;

-- Logs
-- actor_email column exists by design in this package; add if needed:
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='log' AND column_name='actor_email') THEN
    ALTER TABLE log ADD COLUMN actor_email VARCHAR(255);
  END IF;
END$$;
COMMIT;
