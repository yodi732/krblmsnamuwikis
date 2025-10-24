
-- (옵션) 스키마 보강 예시

-- 1) 사용자 테이블에 관리자 플래그가 없다면 추가
-- ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

-- 2) Document 트리 구조용 parent_id
-- ALTER TABLE document ADD COLUMN IF NOT EXISTS parent_id INTEGER NULL;
-- ALTER TABLE document ADD CONSTRAINT document_parent_fk
--   FOREIGN KEY (parent_id) REFERENCES document(id) ON DELETE SET NULL;
