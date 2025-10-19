-- 로그인 500 오류(UndefinedColumn: user.pw_hash) 해결을 위한 안전한 핫픽스
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='user' AND column_name='pw_hash'
  ) THEN
    ALTER TABLE "user" ADD COLUMN pw_hash VARCHAR(255);
  END IF;
END $$;
