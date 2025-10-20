-- byeollae-wiki DB hotfix (v2)

-- A) document.title UNIQUE: allow ON CONFLICT(title)
CREATE UNIQUE INDEX IF NOT EXISTS ux_document_title ON document (title);

-- B) Rename password_hash -> pw_hash if needed (to match app code)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'user' AND column_name = 'password_hash'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'user' AND column_name = 'pw_hash'
  ) THEN
    EXECUTE 'ALTER TABLE "user" RENAME COLUMN password_hash TO pw_hash';
  END IF;
END;
$$;

-- C) user.email UNIQUE
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_email ON "user" (email);
