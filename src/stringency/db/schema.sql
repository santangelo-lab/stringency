-- stringency trace schema (design 9.4, 9.5). One database per project at prov/run.db.
-- Tables marked append-only get triggers that raise on UPDATE and DELETE.
-- Mutable tables (runs, steps, holds, consensus, artifacts) have status columns whose
-- mutation is coupled to an event row by the store API, not by the schema.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version   INTEGER PRIMARY KEY,
    applied   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    project_id          TEXT PRIMARY KEY,
    path                TEXT NOT NULL,
    pipeline_name       TEXT NOT NULL,
    pipeline_version    TEXT NOT NULL,
    pipeline_digest     TEXT NOT NULL,
    method_repo         TEXT NOT NULL,
    method_tag          TEXT NOT NULL,
    mode                TEXT NOT NULL,
    profile             TEXT NOT NULL,
    owner               TEXT NOT NULL,
    reviewer            TEXT NOT NULL,
    judgment_harness    TEXT NOT NULL,
    executor            TEXT NOT NULL,
    objective_json      TEXT NOT NULL,
    design_json         TEXT NOT NULL,
    splits_json         TEXT,
    created             TEXT NOT NULL,
    stringency_version  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id                  TEXT PRIMARY KEY,
    project_id              TEXT NOT NULL REFERENCES projects(project_id),
    parent_run_id           TEXT REFERENCES runs(run_id),
    fork_at_step            TEXT,
    delta_json              TEXT,
    git_sha                 TEXT NOT NULL,
    git_dirty               INTEGER NOT NULL,
    allow_dirty_reason      TEXT,
    host                    TEXT NOT NULL,
    user                    TEXT NOT NULL,
    operator_harness        TEXT,
    operator_version        TEXT,
    operator_session_ref    TEXT,
    started                 TEXT NOT NULL,
    ended                   TEXT,
    status                  TEXT NOT NULL,
    env_digest              TEXT,
    policy_version          TEXT NOT NULL,
    policy_digest           TEXT NOT NULL,
    stringency_version      TEXT NOT NULL,
    budgets_json            TEXT,                       -- reserved for open mode (design 17)
    kind                    TEXT NOT NULL DEFAULT 'run'  -- run | control
);

CREATE TABLE IF NOT EXISTS run_events (                 -- append-only
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    seq          INTEGER NOT NULL,
    event        TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    ts           TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);

CREATE TABLE IF NOT EXISTS steps (
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    step_id         TEXT NOT NULL,
    module          TEXT NOT NULL,
    module_version  TEXT NOT NULL,
    operation       TEXT NOT NULL,
    status          TEXT NOT NULL,
    attempt         INTEGER NOT NULL DEFAULT 0,
    started         TEXT,
    ended           TEXT,
    PRIMARY KEY (run_id, step_id)
);

CREATE TABLE IF NOT EXISTS step_events (                -- append-only
    run_id       TEXT NOT NULL,
    step_id      TEXT NOT NULL,
    seq          INTEGER NOT NULL,
    event        TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    ts           TEXT NOT NULL,
    PRIMARY KEY (run_id, step_id, seq),
    FOREIGN KEY (run_id, step_id) REFERENCES steps(run_id, step_id)
);

CREATE TABLE IF NOT EXISTS actions (                    -- append-only
    action_id      TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL REFERENCES runs(run_id),
    step_id        TEXT NOT NULL,
    attempt        INTEGER NOT NULL,
    operation      TEXT NOT NULL,
    module         TEXT NOT NULL,
    params_json    TEXT NOT NULL,
    params_hash    TEXT NOT NULL,
    inputs_json    TEXT NOT NULL,
    input_digest   TEXT NOT NULL,
    proposed_by    TEXT NOT NULL,
    rationale_ref  TEXT,
    proposed_at    TEXT NOT NULL,
    param_source_json TEXT NOT NULL DEFAULT '{}',
    ticket         TEXT
);
CREATE INDEX IF NOT EXISTS actions_run_step ON actions(run_id, step_id, attempt);

CREATE TABLE IF NOT EXISTS state_snapshots (            -- append-only
    snapshot_id        TEXT PRIMARY KEY,
    run_id             TEXT NOT NULL REFERENCES runs(run_id),
    step_id            TEXT NOT NULL,
    phase              TEXT NOT NULL,
    extractor          TEXT NOT NULL,
    extractor_version  TEXT NOT NULL,
    summary_json       TEXT NOT NULL,
    digest             TEXT NOT NULL,
    ts                 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS snapshots_run_step ON state_snapshots(run_id, step_id);

CREATE TABLE IF NOT EXISTS predicate_results (          -- append-only
    run_id                 TEXT NOT NULL,                  -- 'init' for init-time verdicts (action_id = project_id)
    action_id              TEXT NOT NULL,
    phase                  TEXT NOT NULL,
    predicate_id           TEXT NOT NULL,
    predicate_version      INTEGER NOT NULL,
    fired                  INTEGER NOT NULL,
    default_disposition    TEXT NOT NULL,
    effective_disposition  TEXT NOT NULL,
    reason                 TEXT,
    evidence_json          TEXT NOT NULL,
    severity               TEXT,
    policy_digest          TEXT NOT NULL,
    ts                     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS predicate_results_action ON predicate_results(action_id, phase);
CREATE INDEX IF NOT EXISTS predicate_results_run ON predicate_results(run_id);

CREATE TABLE IF NOT EXISTS executions (                 -- append-only
    action_id            TEXT NOT NULL,
    runner               TEXT NOT NULL,                  -- engine | operator
    ticket               TEXT,
    env_name             TEXT,
    env_digest           TEXT,
    env_status           TEXT NOT NULL,                  -- verified | as_reported
    command              TEXT,
    exit_code            INTEGER,
    duration_ms          INTEGER,
    stdout_path          TEXT,
    stderr_path          TEXT,
    evidence_paths_json  TEXT NOT NULL DEFAULT '[]',
    observed_params_json TEXT NOT NULL DEFAULT '{}',
    ts                   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS executions_action ON executions(action_id);

CREATE TABLE IF NOT EXISTS holds (
    hold_id             TEXT PRIMARY KEY,
    run_id              TEXT,                            -- NULL for project-level holds (init confirm)
    step_id             TEXT,
    item_id             TEXT,
    kind                TEXT NOT NULL,
    reason              TEXT NOT NULL,
    waits_on_role       TEXT NOT NULL,
    created             TEXT NOT NULL,
    resolved_by_review  TEXT,
    resolved_via        TEXT,
    bound_module_version TEXT,
    bound_input_digest   TEXT,
    bound_params_hash    TEXT,
    bound_item_evidence_digest TEXT,
    context_json        TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS holds_open ON holds(resolved_by_review, run_id);

CREATE TABLE IF NOT EXISTS reviews (                    -- append-only
    review_id                   TEXT PRIMARY KEY,
    hold_id                     TEXT NOT NULL REFERENCES holds(hold_id),
    run_id                      TEXT,
    step_id                     TEXT,
    item_id                     TEXT,
    reviewer                    TEXT NOT NULL,
    host                        TEXT NOT NULL,
    via                         TEXT NOT NULL,           -- tty | relayed | rebind
    operator_session_ref        TEXT,
    ts                          TEXT NOT NULL,
    verdict                     TEXT NOT NULL,           -- accept | override | reject | defer
    correction_json             TEXT,
    reason                      TEXT,
    reason_code                 TEXT,
    bound_module_version        TEXT,
    bound_input_digest          TEXT,
    bound_params_hash           TEXT,
    bound_item_evidence_digest  TEXT,
    chosen_replicate            INTEGER
);
CREATE INDEX IF NOT EXISTS reviews_hold ON reviews(hold_id);
CREATE INDEX IF NOT EXISTS reviews_binding ON reviews(verdict, bound_module_version, bound_input_digest, bound_params_hash);

CREATE TABLE IF NOT EXISTS invocations (                -- append-only
    invocation_id     TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL,
    step_id           TEXT NOT NULL,
    action_id         TEXT NOT NULL,
    replicate         INTEGER NOT NULL,
    template_path     TEXT,
    template_blob     TEXT,
    prompt_hash       TEXT NOT NULL,
    model_requested   TEXT,
    model_resolved    TEXT,
    harness_kind      TEXT NOT NULL,
    harness_version   TEXT,
    via               TEXT NOT NULL,                     -- direct | subagent
    isolation         TEXT NOT NULL,                     -- enforced | as_reported
    nonce             TEXT,
    nonce_ok          INTEGER,
    request_path      TEXT,
    response_path     TEXT,
    reported_json     TEXT,
    sampling_json     TEXT,
    response_hash     TEXT,
    schema_valid      INTEGER NOT NULL,
    tokens_in         INTEGER,
    tokens_out        INTEGER,
    duration_ms       INTEGER,
    bit_reproducible  INTEGER NOT NULL DEFAULT 0,
    tool_calls_json   TEXT NOT NULL DEFAULT '[]',
    ts                TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS invocations_step ON invocations(run_id, step_id);

CREATE TABLE IF NOT EXISTS messages (                   -- content-addressed, append-only
    hash  TEXT PRIMARY KEY,
    text  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS judgments (                  -- append-only
    run_id            TEXT NOT NULL,
    step_id           TEXT NOT NULL,
    item_id           TEXT NOT NULL,
    replicate         INTEGER NOT NULL,
    label             TEXT,
    ontology_id       TEXT,
    confidence        TEXT,
    abstain           INTEGER,
    supporting_json   TEXT NOT NULL DEFAULT '[]',
    contradicting_json TEXT NOT NULL DEFAULT '[]',
    rationale_ref     TEXT,
    schema_valid      INTEGER NOT NULL,
    extra_json        TEXT NOT NULL DEFAULT '{}',
    attempt           INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS judgments_step ON judgments(run_id, step_id, item_id);

CREATE TABLE IF NOT EXISTS consensus (
    run_id                    TEXT NOT NULL,
    step_id                   TEXT NOT NULL,
    item_id                   TEXT NOT NULL,
    label                     TEXT,
    ontology_id               TEXT,
    source                    TEXT NOT NULL,             -- agreed | accepted | override | unresolved
    replicate_labels_json     TEXT NOT NULL,
    replicate_confidence_json TEXT NOT NULL,
    review_id                 TEXT,
    PRIMARY KEY (run_id, step_id, item_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id            TEXT PRIMARY KEY,
    run_id                 TEXT NOT NULL,
    step_id                TEXT NOT NULL,
    action_id              TEXT,
    path                   TEXT NOT NULL,
    hash                   TEXT NOT NULL,
    size                   INTEGER NOT NULL,
    kind                   TEXT NOT NULL,
    is_final               INTEGER NOT NULL DEFAULT 0,
    provisional            INTEGER NOT NULL DEFAULT 0,
    sidecar_path           TEXT,
    operator_session_ref   TEXT,
    operator_artifact_ref  TEXT,
    name                   TEXT,
    status                 TEXT NOT NULL DEFAULT 'produced'   -- produced | rejected
);
CREATE INDEX IF NOT EXISTS artifacts_step ON artifacts(run_id, step_id);

CREATE TABLE IF NOT EXISTS controls_runs (              -- append-only
    control_run_id  TEXT PRIMARY KEY,
    module          TEXT NOT NULL,
    module_version  TEXT NOT NULL,
    control_name    TEXT NOT NULL,
    kind            TEXT NOT NULL,
    run_id          TEXT,
    passed          INTEGER NOT NULL,
    metrics_json    TEXT NOT NULL,
    ts              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (                 -- append-only
    delivery_id    TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL,
    path           TEXT NOT NULL,
    coverage_hash  TEXT NOT NULL,
    methods_hash   TEXT NOT NULL,
    index_hash     TEXT NOT NULL,
    ts             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_snapshots (
    policy_digest       TEXT PRIMARY KEY,
    policy_version      TEXT NOT NULL,
    content_json        TEXT NOT NULL,
    predicate_set_json  TEXT NOT NULL,
    first_seen          TEXT NOT NULL
);

-- Append-only enforcement (design 9.5).
CREATE TRIGGER IF NOT EXISTS ao_run_events_u BEFORE UPDATE ON run_events BEGIN SELECT RAISE(ABORT, 'run_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_run_events_d BEFORE DELETE ON run_events BEGIN SELECT RAISE(ABORT, 'run_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_step_events_u BEFORE UPDATE ON step_events BEGIN SELECT RAISE(ABORT, 'step_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_step_events_d BEFORE DELETE ON step_events BEGIN SELECT RAISE(ABORT, 'step_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_actions_u BEFORE UPDATE ON actions BEGIN SELECT RAISE(ABORT, 'actions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_actions_d BEFORE DELETE ON actions BEGIN SELECT RAISE(ABORT, 'actions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_state_snapshots_u BEFORE UPDATE ON state_snapshots BEGIN SELECT RAISE(ABORT, 'state_snapshots is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_state_snapshots_d BEFORE DELETE ON state_snapshots BEGIN SELECT RAISE(ABORT, 'state_snapshots is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_predicate_results_u BEFORE UPDATE ON predicate_results BEGIN SELECT RAISE(ABORT, 'predicate_results is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_predicate_results_d BEFORE DELETE ON predicate_results BEGIN SELECT RAISE(ABORT, 'predicate_results is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_executions_u BEFORE UPDATE ON executions BEGIN SELECT RAISE(ABORT, 'executions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_executions_d BEFORE DELETE ON executions BEGIN SELECT RAISE(ABORT, 'executions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_reviews_u BEFORE UPDATE ON reviews BEGIN SELECT RAISE(ABORT, 'reviews is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_reviews_d BEFORE DELETE ON reviews BEGIN SELECT RAISE(ABORT, 'reviews is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_invocations_u BEFORE UPDATE ON invocations BEGIN SELECT RAISE(ABORT, 'invocations is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_invocations_d BEFORE DELETE ON invocations BEGIN SELECT RAISE(ABORT, 'invocations is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_messages_u BEFORE UPDATE ON messages BEGIN SELECT RAISE(ABORT, 'messages is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_messages_d BEFORE DELETE ON messages BEGIN SELECT RAISE(ABORT, 'messages is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_judgments_u BEFORE UPDATE ON judgments BEGIN SELECT RAISE(ABORT, 'judgments is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_judgments_d BEFORE DELETE ON judgments BEGIN SELECT RAISE(ABORT, 'judgments is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_controls_runs_u BEFORE UPDATE ON controls_runs BEGIN SELECT RAISE(ABORT, 'controls_runs is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_controls_runs_d BEFORE DELETE ON controls_runs BEGIN SELECT RAISE(ABORT, 'controls_runs is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_deliveries_u BEFORE UPDATE ON deliveries BEGIN SELECT RAISE(ABORT, 'deliveries is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_deliveries_d BEFORE DELETE ON deliveries BEGIN SELECT RAISE(ABORT, 'deliveries is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_policy_snapshots_u BEFORE UPDATE ON policy_snapshots BEGIN SELECT RAISE(ABORT, 'policy_snapshots is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ao_policy_snapshots_d BEFORE DELETE ON policy_snapshots BEGIN SELECT RAISE(ABORT, 'policy_snapshots is append-only'); END;
