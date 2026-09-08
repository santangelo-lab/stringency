"""Review display (design 7.3, improvements A1 through A3): a golden render per hold kind, the
hold id in every hold message, `review --hold`, and `init` exiting 10 on its open confirm hold."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from stringency.predicates.context import EvidenceTable
from stringency.project import Project
from stringency.review import queue, show
from stringency.review_render import resolve_ref
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_review import held_project
from tests.test_run import cli

GOLDEN = Path(__file__).parent / "golden"
ULID = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")


def normalize(text: str, project: Project) -> str:
    text = text.replace(str(project.root), "<root>")
    text = ULID.sub("<id>", text)
    text = re.sub(r"blake3:[0-9a-f]{64}", "blake3:<digest>", text)
    text = re.sub(r"\b[0-9a-f]{64}\b", "<sha256>", text)
    return re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", "<ts>", text)


def check_golden(request: pytest.FixtureRequest, name: str, text: str) -> None:
    golden = GOLDEN / f"review_{name}.txt"
    if request.config.getoption("--update-golden"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(text + "\n")
    assert text + "\n" == golden.read_text(), f"render differs from {golden.name}"


@pytest.fixture(autouse=True)
def _tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


# -- golden renders ---------------------------------------------------------------------------


def test_confirm_render(request: pytest.FixtureRequest, project: Project) -> None:
    h = project.confirm_hold()
    view = show(project, h)
    assert "Echo-back" in view.text and "design.yml:" in view.text
    assert f"--verdict accept --hold {h['hold_id']}" in view.text
    check_golden(request, "confirm", normalize(view.text, project))


def test_run_disagreement_render(request: pytest.FixtureRequest, make_project: InitFn) -> None:
    p, _ = held_project(make_project, "split.yml")
    h = queue(p)[0]
    assert h["kind"] == "run_disagreement"
    view = show(p, h)
    assert "calls by label:" in view.text
    assert "abundant: replicate 1, 2" in view.text and "uniform: replicate 3" in view.text
    assert "evidence row in summary:" in view.text and "mean_value=" in view.text
    assert 'rationale: "sd ' in view.text  # quoted, not summarized
    assert "summary[A].mean_value = " in view.text  # cited cell shown as the stored value
    assert f"--verdict accept --hold {h['hold_id']} --replicate <n>" in view.text
    check_golden(request, "run_disagreement", normalize(view.text, p))


def test_self_uncertain_render(request: pytest.FixtureRequest, make_project: InitFn) -> None:
    p, _ = held_project(make_project, "one_abstain.yml")
    h = queue(p)[0]
    assert h["kind"] == "self_uncertain"
    view = show(p, h)
    assert "replicate 2: abstain" in view.text
    assert "supporting:\n      none" in view.text
    check_golden(request, "self_uncertain", normalize(view.text, p))


def test_judgment_predicate_flag_render(
    request: pytest.FixtureRequest, make_project: InitFn
) -> None:
    """The toy-cs pattern: unanimous labels, context cells cited as contradicting evidence."""
    p, _ = held_project(make_project, "context_contradicting.yml")
    holds = queue(p)
    assert [h["kind"] for h in holds] == ["flag"]
    h = holds[0]
    view = show(p, h)
    assert "predicate judg.confidence_consistent@1  phase post" in view.text
    assert "flagged replicates and items:" in view.text
    assert "replicate 1, item A: abundant (medium)" in view.text
    assert "criterion for medium: at least 2 supporting, at most 1 contradicting" in view.text
    assert "criterion for high: at least 3 supporting, at most 0 contradicting" in view.text
    assert "summary[C].mean_value = " in view.text  # the context cell, resolved
    assert "evidence table (rows cited) summary:" in view.text
    assert len(view.flagged) == 6 and view.flagged[0]["call"] == "abundant (medium)"
    assert "{" not in view.text.split("verdicts:")[0]  # no raw JSON before the verdict block
    check_golden(request, "judgment_flag", normalize(view.text, p))


def test_predicate_flag_render(request: pytest.FixtureRequest, make_project: InitFn) -> None:
    """A flag on a non-judgment predicate: repro.env_unverified under strict, operator runner."""
    from stringency.operator_exec.submit import submit
    from stringency.operator_exec.tickets import job_spec
    from stringency.runs import open_or_resume
    from stringency.steps import propose
    from tests.test_steps import play_agent

    p = make_project(profile="strict")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    rc = open_or_resume(p)
    prop = propose(rc, "01_filter")
    outputs, log = play_agent(job_spec(prop, None))
    assert submit(rc, prop.ticket or "", outputs, [log]).status == "held"
    h = queue(p)[0]
    view = show(p, h)
    assert "predicate repro.env_unverified@1  phase post" in view.text
    assert "parameters: min_value=" in view.text
    assert "execution: runner=operator" in view.text and "env_status=as_reported" in view.text
    assert "state the gate read (after 01_filter):" in view.text
    assert "the step is completed" in view.text  # post-phase accept effect
    check_golden(request, "flag", normalize(view.text, p))


def test_cited_cell_resolution() -> None:
    table = EvidenceTable(
        "summary", "group", ("group", "mean_value"), {"A": {"group": "A", "mean_value": 74.82}}
    )
    tables = {"summary": table}
    ok = resolve_ref(
        tables, {"table": "summary", "row": "A", "column": "mean_value", "value": "74.82"}
    )
    assert ok.matches and ok.line() == "summary[A].mean_value = 74.82"
    off = resolve_ref(
        tables, {"table": "summary", "row": "A", "column": "mean_value", "value": 74.8}
    )
    assert not off.matches and off.line() == "summary[A].mean_value: cited 74.8, stored 74.82"
    gone = resolve_ref(tables, {"table": "summary", "row": "Z", "column": "mean_value", "value": 1})
    assert not gone.resolves and gone.line().endswith("(no such cell)")
    other = resolve_ref(tables, {"table": "other", "row": "A", "column": "x", "value": 1})
    assert not other.resolves


# -- review --hold, hold messages, init exit code ------------------------------------------------


def test_review_hold_shows_one_hold(make_project: InitFn) -> None:
    p, _ = held_project(make_project, "split.yml")
    h = queue(p)[0]
    r = cli(p, "review", "--hold", h["hold_id"])
    assert r.exit_code == 0, r.output
    assert r.output.startswith(f"hold {h['hold_id']}  kind run_disagreement")
    r = cli(p, "review", "--hold", h["hold_id"], "--json")
    out = json.loads(r.output)
    assert out["schema"] == "stringency.review_queue/1" and len(out["holds"]) == 1
    view = out["holds"][0]
    assert view["text"].startswith("hold ") and view["verdicts"][0]["verdict"] == "accept"
    assert view["replicates"][0]["supporting"][0]["stored"] is not None
    assert view["evidence_rows"]["summary"]["A"]["group"] == "A"
    r = cli(p, "review", "--hold", "01NOSUCHHOLD00000000000000")
    assert r.exit_code == 15


def test_review_hold_shows_resolved_hold(project: Project) -> None:
    h = project.confirm_hold()
    accept_hold(project.store, h["hold_id"])
    r = cli(project, "review", "--hold", h["hold_id"])
    assert r.exit_code == 0 and "resolved by review" in r.output and "via tty" in r.output


def test_run_hold_message_names_hold_and_command(make_project: InitFn) -> None:
    p, env = held_project(make_project, "split.yml", owner="alice", reviewer="bob")
    h = queue(p)[0]
    r = cli(p, "run", env=env)
    assert r.exit_code == 10
    msg = r.output + str(r.stderr)
    assert f"held: hold {h['hold_id']} (run_disagreement on 03_label item A)" in msg
    assert "waits on reviewer bob" in msg
    assert f"run `stringency review --hold {h['hold_id']}` in {p.root}" in msg
    r = cli(p, "next", "--json")
    assert json.loads(r.output)["message"] == msg.strip().splitlines()[-1]


def test_run_before_confirm_names_hold_and_owner(make_project: InitFn) -> None:
    p = make_project(owner="alice", reviewer="bob")
    h = p.confirm_hold()
    r = cli(p, "run")
    assert r.exit_code == 10
    msg = r.output + str(r.stderr)
    assert f"held: hold {h['hold_id']} (confirm); waits on owner alice" in msg
    assert f"stringency review --hold {h['hold_id']}" in msg
    r = cli(p, "status")
    assert f"hold {h['hold_id']} (confirm) waits on owner alice" in r.output


def test_init_exits_10_with_open_confirm_hold(
    tmp_path: Path, method_repo: MethodRepo, declarations: dict[str, Path]
) -> None:
    from typer.testing import CliRunner

    from stringency.cli.app import app

    args = [
        "init",
        str(tmp_path / "cli-proj"),
        "--method",
        method_repo.spec,
        "--pipeline",
        "toy",
        "--objective",
        str(declarations["objective.yml"]),
        "--design",
        str(declarations["design.yml"]),
        "--inputs",
        str(declarations["inputs.yml"]),
        "--owner",
        "t",
        "--judgment-harness",
        "mock",
        "--executor",
        "local",
        "--json",
    ]
    r = CliRunner().invoke(app, args)
    assert r.exit_code == 10, r.output
    out = json.loads(r.output)
    assert out["schema"] == "stringency.init/1" and out["confirm_hold"]
    p = Project.load(tmp_path / "cli-proj")
    assert p.confirm_hold()["hold_id"] == out["confirm_hold"]
    accept_hold(p.store, out["confirm_hold"], reviewer="t")
    # the run that follows the accepted echo-back is not held by init's hold
    r = cli(p, "status")
    assert r.exit_code == 0 and "confirm accepted" in r.output


# -- A4: the review packet on disk ------------------------------------------------------------


def test_packet_written_when_hold_opens(make_project: InitFn) -> None:
    p, env = held_project(make_project, "split.yml")
    h = queue(p)[0]
    view = show(p, h)
    md = p.step_dir(h["run_id"], "03_label") / "review" / f"{h['hold_id']}.md"
    page = md.with_suffix(".html")
    assert md.exists() and page.exists()
    assert view.packet == md
    text = md.read_text()
    assert text.startswith(f"# Hold {h['hold_id']} (run_disagreement) on step 03_label, item A\n")
    assert "```\n" + view.text + "\n```\n" in text  # the packet is the review render verbatim
    html = page.read_text()
    assert "<script" not in html and "<style>" in html
    assert f"<title>stringency hold {h['hold_id']}</title>" in html
    assert "summary[A].mean_value = 74.82" in html and "&#39;" in html  # escaped, not raw
    assert not (md.parent / f"{h['hold_id']}.md.stringency.json").exists()  # no sidecar
    r = cli(p, "run", env=env)
    assert r.exit_code == 10 and f"; packet {md}" in (r.output + str(r.stderr))
    out = json.loads(cli(p, "review", "--hold", h["hold_id"], "--json").output)
    assert out["holds"][0]["packet"] == str(md)


def test_packet_for_post_flag_and_none_for_confirm(make_project: InitFn) -> None:
    p, _ = held_project(make_project, "context_contradicting.yml")
    h = queue(p)[0]
    md = p.step_dir(h["run_id"], "03_label") / "review" / f"{h['hold_id']}.md"
    assert md.exists() and "criterion for medium" in md.read_text()
    p2 = make_project()
    c = p2.confirm_hold()
    assert show(p2, c).packet is None
    assert not list(p2.root.rglob("review/*.md"))  # the echo-back is the confirm hold's packet
