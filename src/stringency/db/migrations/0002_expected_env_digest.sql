-- C1 (2026-09-08): keep the manifest's expected digest apart from the verified one.
-- `env_digest` is null unless env_status = 'verified'; `expected_env_digest` is what the run
-- resolved for the module's env at open.
ALTER TABLE executions ADD COLUMN expected_env_digest TEXT;
