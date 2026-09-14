stringency coverage report
run 01M2GJRNPDFVVWJ4GW76M44Q9W | project 01M2GJN5Q8PX0C14MSC6TQVACD | pipeline toy-engine@0.1.1 | mode pipeline | profile standard
policy 0.1.0 (blake3:8f946ad4a256) | stringency 0.1.0.dev0 | method b5b0e27c1f88 (clean)

steps: 5 declared, 5 completed, 0 held, 0 blocked, 0 rejected, 0 failed

gate: 34 predicates registered; 23 in scope for this pipeline; 23 evaluated over 5 steps, both phases
  fired: 0 block, 0 flag, 0 log
  decision points without predicate coverage:
    none
  ungated steps: none

judgment:
  label-groups@0.1.1: 3 items x 3 replicates; 3 agreed, 0 self_uncertain, 0 run_disagreement
    reviews: 0 accepted, 0 override, 0 unresolved; override rate this run 0/3; cumulative for this module version 0/3

controls (last passing run per module version):
  none recorded

execution:
  2 steps operator-run (env verified 2, as reported 0: ), 3 engine-run; 0 plan drift

reproducibility:
  seeds set on 0/0 stochastic steps; env digest 46c71e1a21bf1f3edcb05fe3e4fba6f904d7be93a2e34d78c8e92faaa6655d92
  judgment invocations stored (3), not bit-reproducible; via subagent, isolation as_reported; model as reported: claude-opus-5

not checked: anything not listed above
