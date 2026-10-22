#!/usr/bin/env python3
"""Run Latch benchmark evals (scBench, SpatialBench) through Claude Code on this machine, without
Docker, and grade them with `latch-eval-tools` (`spec/plans/benchmark-plan.md`, Phase 0).

The agent command is the one `latch_eval_tools.harness.claudecode` builds (`--print
--dangerously-skip-permissions --effort max --verbose --output-format stream-json
--include-partial-messages --thinking-display summarized --model <m>`), the prompt is the task
plus the packaged data instructions plus the background-process note, and the layout is
Latch's (`<run>/agent_workspace/data/<file>`, `eval_answer.json`, `trajectory.json`,
`result.json`), so a run here reads like a published trajectory. The one difference: the agent
runs inside the benchmark image under apptainer (`--image`), or on the host (`--no-image`),
instead of a Docker container. Memory is not capped (apptainer needs cgroup delegation for
that); the host has 500 GB.

Usage:
  run_eval.py --eval <eval.json> [--replicates 3] [--model claude-opus-5-5] --out <dir>
              [--image <sif>] [--arm baseline] [--system-prompt-file <f>] [--max-turns N]
  run_eval.py --summary <dir>...     # one CSV over every result.json below the directories

Needs: the eval's data in the Latch cache (`latch login` once, then this script downloads
through the SDK), `claude` on PATH logged in, the venv with latch-eval-tools.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

CLAUDE_FLAGS = [
    "--print",
    "--dangerously-skip-permissions",
    "--effort",
    "max",
    "--verbose",
    "--output-format",
    "stream-json",
    "--include-partial-messages",
    "--thinking-display",
    "summarized",
]
BACKGROUND_PROCESS_NOTE = (
    "\n\nNote: Do not end your turn while a background process is still"
    " running. Nothing will alert you it is done. Ending your turn may"
    " complete the session and kill the process; instead, block"
    " synchronously and poll until the job finishes before returning."
)
EVAL_TIMEOUT = 6000


def data_instructions() -> str:
    from latch_eval_tools.harness.utils import load_data_instructions

    return load_data_instructions()


def stage_data(eval_json: dict, agent_dir: Path) -> list[Path]:
    """The eval's data node(s) into `agent_workspace/data/`, from the SDK cache."""
    from latch_eval_tools.harness.utils import download_single_dataset

    nodes = eval_json.get("data_node") or []
    nodes = nodes if isinstance(nodes, list) else [nodes]
    data_dir = agent_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for node in nodes:
        cached = download_single_dataset(node, show_progress=True)
        dst = data_dir / cached.name
        if not dst.exists():
            if cached.is_dir():
                shutil.copytree(cached, dst)
            else:
                os.link(
                    cached, dst
                ) if cached.stat().st_dev == data_dir.stat().st_dev else shutil.copy2(cached, dst)
        out.append(dst)
    return out


def claude_command(model: str, system_prompt: str | None, max_turns: int) -> list[str]:
    cmd = ["claude", *CLAUDE_FLAGS]
    if max_turns > 0:
        cmd += ["--max-turns", str(max_turns)]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    cmd += ["--model", model]
    return cmd


def run_agent(
    agent_dir: Path,
    prompt: str,
    model: str,
    image: Path | None,
    system_prompt: str | None,
    max_turns: int,
    timeout: int,
) -> dict:
    """One Claude Code session over the workspace; the stream-json events to trajectory.json;
    the final `result` event's usage and cost returned."""
    cmd = claude_command(model, system_prompt, max_turns)
    if image is not None:
        cmd = [
            "apptainer",
            "exec",
            "--cleanenv",
            "--env",
            "HOME=/root",
            "--bind",
            f"{agent_dir}:/workspace",
            "--bind",
            f"{Path.home() / '.claude'}:/root/.claude",
            "--bind",
            f"{Path.home() / '.claude.json'}:/root/.claude.json",
            "--env",
            "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1",
            "--pwd",
            "/workspace",
            str(image),
            *cmd,
        ]
        cwd = None
    else:
        cwd = agent_dir
    env = {**os.environ, "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"}
    t0 = time.monotonic()
    events: list[dict] = []
    log = agent_dir.parent / "agent_output.log"
    timed_out = False
    with open(agent_dir.parent / "trajectory.jsonl", "w") as traj, open(log, "w") as lf:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=lf,
            text=True,
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(prompt)
        proc.stdin.close()
        try:
            for line in proc.stdout:
                traj.write(line)
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                events.append(ev)
                if time.monotonic() - t0 > timeout:
                    proc.kill()
                    timed_out = True
                    break
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            timed_out = True
    duration = time.monotonic() - t0
    (agent_dir.parent / "trajectory.json").write_text(json.dumps(events, indent=1))
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    return {
        "duration_s": round(duration, 2),
        "timed_out": timed_out,
        "exit_code": proc.returncode,
        "n_turns": result.get("num_turns"),
        "total_cost": result.get("total_cost_usd"),
        "usage": result.get("usage"),
        "model_usage": result.get("modelUsage"),
        "session_id": result.get("session_id"),
        "subtype": result.get("subtype"),
        "command": cmd,
    }


def run_one(
    eval_path: Path,
    out: Path,
    rep: int,
    model: str,
    image: Path | None,
    system_prompt: str | None,
    max_turns: int,
    timeout: int,
    arm: str,
) -> dict:
    from latch_eval_tools import EvalRunner

    eval_json = json.loads(eval_path.read_text())
    run_dir = out / eval_json["id"] / f"r{rep}"
    agent_dir = run_dir / "agent_workspace"
    if (run_dir / "result.json").exists():
        print(f"skip {run_dir}: result.json exists")
        return json.loads((run_dir / "result.json").read_text())
    agent_dir.mkdir(parents=True, exist_ok=True)
    stage_data(eval_json, agent_dir)
    prompt = f"{eval_json['task']}\n{data_instructions()}{BACKGROUND_PROCESS_NOTE}"
    (run_dir / "prompt.md").write_text(prompt)
    meta: dict = {}

    def agent(task_prompt: str, work_dir: Path) -> dict:
        nonlocal meta
        meta = run_agent(agent_dir, prompt, model, image, system_prompt, max_turns, timeout)
        answer_file = agent_dir / "eval_answer.json"
        answer = {}
        if answer_file.exists():
            try:
                answer = json.loads(answer_file.read_text())
            except json.JSONDecodeError:
                answer = {}
        (run_dir / "eval_answer.json").write_text(json.dumps(answer, indent=2))
        return {"answer": answer, "metadata": meta}

    runner = EvalRunner(str(eval_path))
    res = runner.run(agent_function=agent)
    gr = res.get("grader_result")
    record = {
        "arm": arm,
        "harness": "claude-code (local, apptainer)" if image else "claude-code (local, host)",
        "model_name": model,
        "eval_id": eval_json["id"],
        "replicate": rep,
        "passed": bool(gr.passed) if gr else None,
        "score": getattr(gr, "score", None) if gr else None,
        "reasoning": getattr(gr, "reasoning", None) if gr else None,
        "agent_answer": res.get("agent_answer"),
        "metadata": meta,
        "image": str(image) if image else None,
        "eval_path": str(eval_path),
    }
    (run_dir / "result.json").write_text(json.dumps(record, indent=2, default=str))
    print(
        f"{eval_json['id']} r{rep}: {'PASS' if record['passed'] else 'FAIL'} cost {meta.get('total_cost')} turns {meta.get('n_turns')} {meta.get('duration_s')}s"
    )
    return record


def summary(dirs: list[Path]) -> None:
    rows = []
    for d in dirs:
        for rj in sorted(d.rglob("result.json")):
            r = json.loads(rj.read_text())
            if "eval_id" not in r:
                continue
            m = r.get("metadata") or {}
            u = m.get("usage") or {}
            rows.append(
                {
                    "arm": r["arm"],
                    "model": r["model_name"],
                    "eval": r["eval_id"],
                    "rep": r["replicate"],
                    "passed": int(bool(r["passed"])),
                    "score": r.get("score"),
                    "cost_usd": m.get("total_cost"),
                    "turns": m.get("n_turns"),
                    "duration_s": m.get("duration_s"),
                    "input_tokens": u.get("input_tokens"),
                    "output_tokens": u.get("output_tokens"),
                    "cache_read": u.get("cache_read_input_tokens"),
                    "cache_create": u.get("cache_creation_input_tokens"),
                    "timed_out": m.get("timed_out"),
                }
            )
    w = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()) if rows else ["none"])
    w.writeheader()
    for r in rows:
        w.writerow(r)
    by: dict[tuple, list[int]] = {}
    for r in rows:
        by.setdefault((r["arm"], r["model"], r["eval"]), []).append(r["passed"])
    print()
    print("per eval (mean pass over replicates):")
    means = []
    for k, v in sorted(by.items()):
        print(f"  {k[0]:10} {k[1]:18} {k[2]:50} {sum(v)}/{len(v)}")
        means.append(sum(v) / len(v))
    if len(means) > 1:
        mean = statistics.mean(means)
        sd = statistics.stdev(means)
        t = {
            2: 12.706,
            3: 4.303,
            4: 3.182,
            5: 2.776,
            6: 2.571,
            7: 2.447,
            8: 2.365,
            9: 2.306,
            10: 2.262,
        }.get(len(means), 1.96)
        half = t * sd / math.sqrt(len(means))
        print(
            f"accuracy over evals (t-distribution over per-eval means, as Latch reports): {100 * mean:.1f}% [{100 * (mean - half):.1f}, {100 * (mean + half):.1f}]"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--eval", action="append", type=Path, help="an eval JSON; repeatable")
    ap.add_argument("--replicates", type=int, default=3)
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--image", type=Path, help="the benchmark agent image (.sif); omit with --no-image"
    )
    ap.add_argument("--no-image", action="store_true", help="run claude on the host")
    ap.add_argument("--arm", default="baseline")
    ap.add_argument("--system-prompt-file", type=Path)
    ap.add_argument("--max-turns", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=EVAL_TIMEOUT)
    ap.add_argument("--summary", nargs="*", type=Path)
    args = ap.parse_args()
    if args.summary is not None:
        summary(args.summary)
        return 0
    if not args.eval or not args.out:
        ap.error("--eval and --out are required")
    if not args.no_image and not args.image:
        ap.error("--image <sif> or --no-image")
    system_prompt = args.system_prompt_file.read_text() if args.system_prompt_file else None
    for ev in args.eval:
        for rep in range(1, args.replicates + 1):
            run_one(
                ev,
                args.out,
                rep,
                args.model,
                None if args.no_image else args.image,
                system_prompt,
                args.max_turns,
                args.timeout,
                args.arm,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
