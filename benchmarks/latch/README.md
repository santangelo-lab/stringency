# Latch benchmarks

`run_eval.py` runs Latch's public evals (scBench, SpatialBench) through Claude Code on the lab
workstation and grades them with `latch-eval-tools`, without Docker (`spec/plans/
benchmark-plan.md`). The command, prompt and run layout are the ones Latch's Claude Code
harness uses, so a run reads like a published trajectory.

    cd /lab/projects/2026-10_stringency-benchmark_jrrose5
    .venv/bin/latch login                      # once; a browser flow
    .venv/bin/python <engine>/benchmarks/latch/run_eval.py \
        --eval scbench/evals/qc/bd_rhapsody_tnbc_panel_aware_qc.json \
        --replicates 3 --model claude-opus-5-5 --image images/benchmark_agent.sif \
        --out runs/baseline
    .venv/bin/python <engine>/benchmarks/latch/run_eval.py --summary runs/baseline

`--no-image` runs the agent on the host instead of inside Latch's image. `--arm` labels the
run, `--system-prompt-file` is the method-as-prompt arm. The stringency and sham arms are
added beside the baseline in Phase 2.
