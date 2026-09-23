"""Notify on hold (Track 1h, `spec/plans/project-page-and-notify.md` section 4): one message per
hold or run per event, through the person's own channels, never touching a verb's exit code.
No network: the `command` channel writes to a file; email and Teams are exercised with fakes."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from stringency import notify
from stringency.cli.app import app
from stringency.notify import Message, log_path, notify_after, page_link, teams_card
from stringency.project import Project
from stringency.runs import open_or_resume
from stringency.steps import propose
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_run import HARNESS, MOCK, cli


def _config(channels: list[dict[str, Any]], **extra: Any) -> Path:
    """Write `$XDG_CONFIG_HOME/stringency/notify.yml` (conftest points XDG at a temp dir)."""
    p = Path(os.environ["XDG_CONFIG_HOME"]) / "stringency" / "notify.yml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump({"notify": 1, "channels": channels, **extra}))
    return p


@pytest.fixture
def sink(tmp_path: Path) -> Path:
    """A `command` channel that appends each message (with its event) to `sink.txt`."""
    out = tmp_path / "sink.txt"
    script = tmp_path / "notify.sh"
    script.write_text(
        '#!/bin/sh\nprintf "[%s %s] " "$STRINGENCY_NOTIFY_EVENT" "$STRINGENCY_NOTIFY_KEY" >> '
        f'"{out}"\ncat >> "{out}"\n'
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    _config([{"kind": "command", "argv": [str(script)]}])
    return out


def _cli_init(tmp_path: Path, method_repo: MethodRepo, declarations: dict[str, Path], **env: str):  # type: ignore[no-untyped-def]
    return CliRunner().invoke(
        app,
        [
            "init",
            str(tmp_path / "notified"),
            "--method",
            method_repo.spec,
            "--pipeline",
            "toy-engine",
            "--objective",
            str(declarations["objective.yml"]),
            "--design",
            str(declarations["design.yml"]),
            "--inputs",
            str(declarations["inputs.yml"]),
            "--owner",
            "tester",
            "--judgment-harness",
            "mock",
            "--execution",
            "engine",
            "--executor",
            "local",
        ],
        env=env or None,
    )


def test_confirm_hold_at_init_sends_once_with_terminal_route(
    tmp_path: Path, method_repo: MethodRepo, declarations: dict[str, Path], sink: Path
) -> None:
    r = _cli_init(tmp_path, method_repo, declarations)
    assert r.exit_code == 10, r.output
    p = Project.load(tmp_path / "notified")
    h = p.confirm_hold()
    text = sink.read_text()
    assert text.count("[hold_opened") == 1
    assert "notified: the analysis paused at the plan. confirm: init echo-back awaits" in text
    assert f"cd {p.root} && stringency review --hold {h['hold_id']}" in text
    log = log_path(p.root).read_text().splitlines()
    assert len(log) == 1 and log[0].split("\t")[1:3] == ["hold_opened", h["hold_id"]]
    assert log[0].endswith("\tok")
    # nothing in the verb's own output changed
    assert "held: hold" in r.output and "notify" not in r.output
    # the same hold is not announced twice, and a resolved hold sends nothing
    assert notify_after(p) == []
    accept_hold(p.store, h["hold_id"])
    assert notify_after(p) == [] and sink.read_text() == text


def test_run_completed_and_delivered_send_once(make_project: InitFn, sink: Path) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    run_id = json.loads(r.output)["run_id"]
    text = sink.read_text()
    assert text.count("[run_completed") == 1 and "[hold_opened" not in text
    assert f"{p.root.name}: Completed: " in text and "The run is complete." in text
    assert f"stringency present --run {run_id}" in text
    assert notify_after(p, run_id=run_id) == []
    r = cli(p, "deliver", "--json")
    assert r.exit_code == 0, r.output
    d = json.loads(r.output)
    text = sink.read_text()
    assert text.count("[delivered") == 1
    names = ", ".join(f["file"] for f in d["files"])
    assert f"{p.root.name}: results delivered: {names}." in text and d["path"] in text
    events = [line.split("\t")[1] for line in log_path(p.root).read_text().splitlines()]
    assert events == ["run_completed", "delivered"]


def test_item_hold_from_run_names_step_title_and_item(make_project: InitFn, sink: Path) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}
    r = cli(p, "run", env=env)
    assert r.exit_code == 10, r.output
    text = sink.read_text()
    assert "the analysis paused at Label the groups (item A). run_disagreement:" in text
    # a second `run` on the same hold does not announce it again
    r = cli(p, "run", env=env)
    assert r.exit_code == 10 and sink.read_text() == text


def test_run_failed_sends_with_plain(make_project: InitFn, sink: Path) -> None:
    p = make_project()
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    rc = open_or_resume(p)
    prop = propose(rc, "01_filter")
    r = cli(p, "submit", prop.ticket or "", "--failed", "--reason", "disk full")
    assert r.exit_code == 13, r.output
    text = sink.read_text()
    assert text.count("[run_failed") == 1
    assert f"{p.root.name}: No step has completed. Stopped: " in text and "failed to run." in text


def test_env_zero_silences_and_missing_file_is_silent(
    make_project: InitFn, sink: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    monkeypatch.setenv("STRINGENCY_NOTIFY", "0")
    assert notify_after(p) == [] and not sink.exists() and not log_path(p.root).exists()
    monkeypatch.delenv("STRINGENCY_NOTIFY")
    (Path(os.environ["XDG_CONFIG_HOME"]) / "stringency" / "notify.yml").unlink()
    assert notify_after(p) == [] and not log_path(p.root).exists()


def test_failing_channel_leaves_exit_code_and_logs_error(
    tmp_path: Path, method_repo: MethodRepo, declarations: dict[str, Path]
) -> None:
    _config([{"kind": "command", "argv": ["/bin/sh", "-c", "echo broken >&2; exit 1"]}])
    r = _cli_init(tmp_path, method_repo, declarations)
    assert r.exit_code == 10, r.output
    p = Project.load(tmp_path / "notified")
    line = log_path(p.root).read_text().splitlines()[0]
    assert "\tcommand:/bin/sh\terror: ValueError: exit 1: broken" in line
    # one attempt per hold per event, even when it failed
    assert notify_after(p) == []
    # a malformed config file is one log line, no exception, no send
    (Path(os.environ["XDG_CONFIG_HOME"]) / "stringency" / "notify.yml").write_text(
        "channels: [{kind: pigeon}]\n"
    )
    assert notify_after(p) == []
    assert "config\t-\t-\terror:" in log_path(p.root).read_text().splitlines()[-1]


def test_page_url_gives_page_routes_and_events_filter(make_project: InitFn, sink: Path) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    _config(
        [{"kind": "command", "argv": [str(sink.parent / "notify.sh")]}],
        page_url="http://127.0.0.1:8766/?t=abc",
        events=["hold_opened", "delivered"],
    )
    sent = notify_after(p)
    h = p.confirm_hold()
    assert [m.event for m in sent] == ["hold_opened"]
    assert sent[0].link == f"http://127.0.0.1:8766/hold/{h['hold_id']}?t=abc"
    assert sent[0].link in sink.read_text()
    accept_hold(p.store, h["hold_id"])
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    assert "[run_completed" not in sink.read_text()  # not in `events`
    assert page_link("http://h:1/?t=x", "/run/R") == "http://h:1/run/R?t=x"


def _msg() -> Message:
    return Message(
        "hold_opened",
        "H1",
        "proj",
        "proj: the analysis paused",
        "proj: paused.",
        "http://x/hold/H1?t=1",
    )


def test_email_channel_builds_one_plain_message(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[Any] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            sent.append(("connect", host, port, timeout))

        def __enter__(self) -> FakeSMTP:
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def starttls(self) -> None:
            sent.append(("starttls",))

        def login(self, user: str, password: str) -> None:
            sent.append(("login", user, password))

        def send_message(self, m: Any) -> None:
            sent.append(("send", m))

    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    notify.send_email(
        {
            "kind": "email",
            "to": ["me@example.edu"],
            "from": "me@example.edu",
            "smtp": {"host": "relay.example.edu", "port": 25},
        },
        _msg(),
    )
    assert sent[0] == ("connect", "relay.example.edu", 25, 5.0)
    m = sent[1][1]
    assert m["To"] == "me@example.edu" and m["Subject"] == "proj: the analysis paused"
    assert m["X-Stringency-Event"] == "hold_opened"
    assert m.get_content() == "proj: paused.\n\nhttp://x/hold/H1?t=1\n"
    assert m.get_content_type() == "text/plain"


def test_email_credentials_need_mode_600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cred = tmp_path / "cred.yml"
    cred.write_text("user: u\npassword: p\n")
    cred.chmod(0o644)
    calls: list[str] = []

    class FakeSMTP:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> FakeSMTP:
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def starttls(self) -> None:
            calls.append("starttls")

        def login(self, user: str, password: str) -> None:
            calls.append(f"login {user}")

        def send_message(self, m: Any) -> None:
            calls.append("send")

    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    ch = {
        "kind": "email",
        "to": "me@example.edu",
        "smtp": {"host": "smtp.office365.com", "port": 587, "starttls": True},
        "credentials": str(cred),
    }
    with pytest.raises(ValueError, match="mode 600"):
        notify.send_email(ch, _msg())
    assert calls == ["starttls"]
    cred.chmod(0o600)
    notify.send_email(ch, _msg())
    assert calls == ["starttls", "starttls", "login u", "send"]


def test_teams_webhook_posts_one_adaptive_card(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Any] = []

    class FakeResponse:
        status = 202

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *a: object) -> None:
            pass

    def fake_urlopen(req: Any, timeout: float) -> FakeResponse:
        seen.append(
            (req.full_url, req.get_method(), req.get_header("Content-type"), req.data, timeout)
        )
        return FakeResponse()

    monkeypatch.setattr(notify, "urlopen", fake_urlopen)
    notify.send_teams({"kind": "teams_webhook", "url": "https://prod.logic.azure.com/wf"}, _msg())
    url, method, ctype, data, timeout = seen[0]
    assert (url, method, ctype, timeout) == (
        "https://prod.logic.azure.com/wf",
        "POST",
        "application/json",
        5.0,
    )
    card = json.loads(data)["attachments"][0]
    assert card["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert card["content"]["actions"][0]["url"] == "http://x/hold/H1?t=1"
    assert card["content"]["body"][1]["text"] == "proj: paused."
    with pytest.raises(ValueError, match="https"):
        notify.send_teams({"kind": "teams_webhook", "url": "http://plain"}, _msg())
    # a terminal route (no page) goes in the card body, not an OpenUrl action
    m = _msg()
    m.link = "cd /p && stringency review --hold H1"
    c = teams_card(m)["attachments"][0]["content"]
    assert "actions" not in c and c["body"][-1]["text"] == m.link
