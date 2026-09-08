stringency coverage report
run 01M2172HKP6E3RNQNEPP6DSFCE | project 01M216V6NKHXFHVTY88FSBP4S4 | pipeline toy@0.1.0 | mode pipeline | profile standard
policy 0.1.0 (blake3:f0d8e9011a00) | stringency 0.1.0.dev0 | method 567decf5f3de (clean)

steps: 5 declared, 5 completed, 0 held, 0 blocked, 0 rejected, 0 failed

gate: 33 predicates registered; 22 in scope for this pipeline; 22 evaluated over 5 steps, both phases
  fired: 0 block, 1 flag, 3 log
  flags:
    judg.confidence_consistent@1 03_label       accept    jrrose5    2026-09-08  tty      "labels unanimous; contradicting refs cite context cells, not counter-evidence"
  decision points without predicate coverage:
    none
  ungated steps: none

judgment:
  label-groups@0.1.0: 3 items x 3 replicates; 3 agreed, 0 self_uncertain, 0 run_disagreement
    reviews: 0 accepted, 0 override, 0 unresolved; override rate this run 0/3; cumulative for this module version 0/3

controls (last passing run per module version):
  none recorded

execution:
  3 steps operator-run (env verified 0, as reported 3: 01_filter, 02_summarize, 05_report), 2 engine-run; 0 plan drift

reproducibility:
  seeds set on 0/0 stochastic steps; env digest 46c71e1a21bf1f3edcb05fe3e4fba6f904d7be93a2e34d78c8e92faaa6655d92
  judgment invocations stored (3), not bit-reproducible; via subagent, isolation as_reported; model as reported: claude-opus-5

not checked: anything not listed above
