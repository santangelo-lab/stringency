-- Open mode, the report (2026-10-19): a person marks an answer as a finding, the ones the
-- report leads with. Append-only; the latest row per answer is its state (`mark` or `unmark`).
CREATE TABLE IF NOT EXISTS findings (
    finding_id            TEXT PRIMARY KEY,
    run_id                TEXT NOT NULL REFERENCES runs(run_id),
    question_id           TEXT NOT NULL REFERENCES questions(question_id),
    answer_id             TEXT NOT NULL REFERENCES answers(answer_id),
    action                TEXT NOT NULL,                 -- mark | unmark
    marked_by             TEXT NOT NULL,                 -- the user running the verb
    via                   TEXT NOT NULL,                 -- tty | relayed (as questions.asked_via)
    operator_session_ref  TEXT,
    reason_ref            TEXT,                          -- messages.hash of the person's words
    ts                    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS findings_answer ON findings(run_id, answer_id);
CREATE TRIGGER IF NOT EXISTS ao_findings_u BEFORE UPDATE ON findings BEGIN SELECT RAISE(ABORT, 'findings is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_findings_d BEFORE DELETE ON findings BEGIN SELECT RAISE(ABORT, 'findings is append-only'); END;
