-- A person says, after delivery, that a result is wrong (the beta-tester package, 2026-11-03):
-- one row per flag, append-only, written by `stringency flag`, the console's run page and
-- Stringency Desktop. A flag is a review that happens after delivery with no hold to resolve;
-- it binds to what was on screen (a delivered file by name and hash) so the person never has
-- to name a step. The reason is the person's words, in `messages`.
CREATE TABLE IF NOT EXISTS flags (
    flag_id               TEXT PRIMARY KEY,
    run_id                TEXT NOT NULL REFERENCES runs(run_id),
    step_id               TEXT,                          -- the step the object came from, when known
    object_name           TEXT,                          -- a delivered file's name as index.json lists it
    object_hash           TEXT,                          -- blake3 of that file when flagged
    object_kind           TEXT,                          -- its recorded kind (table, figure, report, ...)
    flagged_by            TEXT NOT NULL,                 -- the account running the verb or serving the page
    host                  TEXT NOT NULL,
    via                   TEXT NOT NULL,                 -- tty | relayed | web (as reviews.via)
    operator_harness      TEXT,
    operator_session_ref  TEXT,
    reason_ref            TEXT NOT NULL,                 -- messages.hash of the person's words
    ts                    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS flags_run ON flags(run_id);
CREATE TRIGGER IF NOT EXISTS ao_flags_u BEFORE UPDATE ON flags BEGIN SELECT RAISE(ABORT, 'flags is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_flags_d BEFORE DELETE ON flags BEGIN SELECT RAISE(ABORT, 'flags is append-only'); END;
