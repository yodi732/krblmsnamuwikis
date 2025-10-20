-- byeollae-wiki DB hotfix: make ON CONFLICT (title) valid
-- Safe to run multiple times.

-- Ensure unique constraint for document.title (required by ON CONFLICT (title))
CREATE UNIQUE INDEX IF NOT EXISTS ux_document_title ON document (title);

-- (Recommended) also ensure unique email for users
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_email ON "user" (email);
