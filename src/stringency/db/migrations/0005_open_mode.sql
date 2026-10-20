-- 2026-10-16 (open_mode_plan.md 2.8): the questions a person asks of a delivered dataset and
-- the answers filed against cited artifacts. Both append-only. `origin` is `person` (their own
-- words) or `suggested` (a path the operator proposed and the person picked); `status` is
-- `admissible` or `blocked` (a blocked answer is kept, as a rejected proposal is). `label` is
-- `trusted` or `untested`, derived from the cited artifacts' lineage when the answer is filed.
CREATE TABLE IF NOT EXISTS questions (
    question_id           TEXT PRIMARY KEY,
    run_id                TEXT NOT NULL REFERENCES runs(run_id),
    seq                   INTEGER NOT NULL,
    text_ref              TEXT NOT NULL,                 -- messages.hash of the person's words
    origin                TEXT NOT NULL,                 -- person | suggested
    asked_via             TEXT NOT NULL,                 -- tty | relayed
    operator_session_ref  TEXT,
    ts                    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS questions_run ON questions(run_id, seq);

CREATE TABLE IF NOT EXISTS answers (
    answer_id        TEXT PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES runs(run_id),
    question_id      TEXT NOT NULL REFERENCES questions(question_id),
    text_ref         TEXT NOT NULL,                      -- messages.hash of the reply text
    cited_json       TEXT NOT NULL,                      -- [{artifact_id, row?, column?}]
    label            TEXT,                               -- trusted | untested; null when blocked
    provenance_json  TEXT NOT NULL,
    status           TEXT NOT NULL,                      -- admissible | blocked
    ts               TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS answers_run ON answers(run_id, question_id);

CREATE TRIGGER IF NOT EXISTS ao_questions_u BEFORE UPDATE ON questions BEGIN SELECT RAISE(ABORT, 'questions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_questions_d BEFORE DELETE ON questions BEGIN SELECT RAISE(ABORT, 'questions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_answers_u BEFORE UPDATE ON answers BEGIN SELECT RAISE(ABORT, 'answers is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_answers_d BEFORE DELETE ON answers BEGIN SELECT RAISE(ABORT, 'answers is append-only'); END;

-- whether an exec step's network was isolated: none (enforced) | unenforced | n/a (a module
-- step, or the local executor)
ALTER TABLE executions ADD COLUMN network TEXT;
