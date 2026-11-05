# 2026-11-05 11:35: the benchmark's run record from the beta's bundle and eval store

**Goal.** The owner's question, asked in the MacBook app session: the beta-tester package's
logging (a bundle per project, an eval store on his machine) might collect the trace data the
benchmark (`spec/plans/benchmark-plan.md`) needs; is it useful? An assessment, written into
the plan; nothing built.

**Done.**
- `spec/plans/benchmark-plan.md`: the section "The run record for Phases 2 to 4": what the
  runner records per replicate today, what a bundle and the eval store hold, the reading
  against the phases, what is not taken, three gaps, where the work lands.
- `spec/plans/PLAN.md`: rows L154 to L156 in the Benchmark table.

**Learned.**
- `latch/run_eval.py` keeps, per replicate, the prompt, the stream-json trajectory, the
  answer file and `result.json` with the grader's verdict, cost, turns and duration; nothing
  of the engine's trace, which Phases 3 and 4 need (hold precision and recall, abstention,
  the override table).
- The beta's eval store already derives what those phases count: holds with `via` (policy
  or a person) and open time, judgments with abstentions and overrides, failures with
  `caught_by` (a predicate by id, replicate disagreement, the judges, a person, nobody), a
  `turns` table from the transcript, recurrence across testers and harnesses. The
  `number_not_delivered` check over the transcript is, for a benchmark answer, the question
  whether the number came from the delivery.
- The bundle locates a transcript only under `~/.claude/projects` by the engine's recorded
  session reference, and caps hits at five; a replicate's trajectory file has the event shape
  the parser reads, so a path flag closes it. The baseline arm has no trace: a hand pass
  through `label.py` is its record.
- `holds.via` makes the plan's open question about policy-accepted confirms a number.

**Altered.** Nothing in code or contracts.

**Open.** L154 to L156, after Phase 2's adapter (L89); the two flags are beta-CLI work in the
beta repository.
