-- 2026-09-09: the hash of the module script as it was when it ran (engine: hashed before
-- running; operator: hashed at submit). exec.script_drift compares it with the hash captured
-- at run open (run_events `captures`.script_blobs).
ALTER TABLE executions ADD COLUMN script_blob TEXT;
