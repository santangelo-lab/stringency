# Trace schema

Design 9.4 with column descriptions, as implemented in `src/stringency/db/schema.sql`. One SQLite
database per project at `prov/run.db`, WAL mode, never on CIFS. Tables marked append-only have
triggers that raise on UPDATE and DELETE. Mutable tables change status only through store methods
that write the matching event row in the same transaction.

| table | append-only | key columns |
|---|---|---|
| `projects` | no | bound configuration at init; `objective_json`, `design_json` as declared |
| `runs` | status mutable | `parent_run_id`, `fork_at_step`, `delta_json` for forks; `git_sha`, `git_dirty`, `allow_dirty_reason`; `operator_*` from `STRINGENCY_OPERATOR*`; `env_digest` over every env used; `policy_version`, `policy_digest`; `kind` (`run`/`control`); `budgets_json` reserved |
| `run_events` | yes | every run status change and capture, `seq` ordered |
| `steps` | status mutable | `module`, `module_version`, `operation`, `status` (design 7.1), `attempt` |
| `step_events` | yes | every transition with `from`/`to`, holds, artifacts, consensus |
| `actions` | yes | one per attempt; `params_json`, `params_hash`, `inputs_json`, `input_digest`, `proposed_by`, `param_source_json`, `rationale_ref` (a `messages` hash), `ticket` |
| `state_snapshots` | yes | the full state JSON after a step (`phase: post`), or the run's initial state (`step_id: run`); `extractor`, `extractor_version`, `digest` |
| `predicate_results` | yes | one row per predicate evaluated, fired or not; `default_disposition`, `effective_disposition`, `reason`, `evidence_json`, `policy_digest`; `run_id = 'init'` for init-time verdicts |
| `executions` | yes | `runner` (`engine`/`operator`), `ticket`, `env_name`, `env_digest` (only when `env_status` is `verified`), `expected_env_digest` (what the run resolved for the env; migration 2), `env_status` (`verified`/`as_reported`), `command` (the engine's argv, or the operator's `--command` as reported), `exit_code`, `duration_ms`, stdout/stderr paths, `evidence_paths_json`, `observed_params_json` |
| `holds` | resolution mutable | `kind` (`flag`, `self_uncertain`, `run_disagreement`, `confirm`), `item_id`, `waits_on_role`, bindings (`bound_*`), `context_json`, `resolved_by_review`, `resolved_via` (`tty`/`relayed`/`rebind`) |
| `reviews` | yes | `reviewer`, `host`, `via`, `operator_session_ref`, `verdict`, `correction_json`, `reason`, `reason_code` (reserved), bindings, `chosen_replicate` |
| `invocations` | yes | per harness call (retries included): template path and blob, `prompt_hash`, models requested and resolved, harness kind and version, `via`, `isolation`, `nonce`, `nonce_ok`, request/response paths, `reported_json` verbatim, `sampling_json`, `response_hash`, `schema_valid`, tokens, duration, `bit_reproducible`, `tool_calls_json` |
| `messages` | yes | content-addressed text: prompts, responses, rationales, evidence tables as shown, review reasons |
| `judgments` | yes | one per item per replicate; `item_id = '*'` with `schema_valid = 0` for an invalid replicate |
| `consensus` | row replaceable | per item: `label`, `ontology_id`, `source` (`agreed`/`accepted`/`override`/`unresolved`), replicate labels and confidences, `review_id` |
| `artifacts` | flags mutable | every engine-written file: `path`, `hash`, `size`, `kind`, `name`, `is_final`, `provisional`, `sidecar_path`, `status` (`produced`/`rejected`), operator cross-links |
| `controls_runs` | yes | per control execution: module and version, control, kind, run, `passed`, `metrics_json` |
| `deliveries` | yes | per `deliver`: path and hashes of coverage, methods, index |
| `policy_snapshots` | yes | every distinct policy digest with its content and predicate set |
| `schema_migrations` | no | forward-only migration log |
