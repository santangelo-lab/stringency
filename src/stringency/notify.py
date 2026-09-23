"""Notify on hold (Track 1h, `spec/plans/project-page-and-notify.md` section 4): one message to
the person running the engine when a run needs them or is finished.

Four events, sent from the verbs that call `refresh_if_present` and wrapped the same way: a send
never changes a verb's exit code or output. `hold_opened` for every open hold not yet announced
(confirm, flag, item), `run_completed`, `delivered`, `run_failed`. Never tickets, dispatches or
proposals: those are the operator's. One message per hold or run id per event, kept by the
per-project log `<project>/.stringency/notify.log` (outside `prov/`, since notifications are not
part of the trace). Configuration is per user, `~/.config/stringency/notify.yml` (or
`$XDG_CONFIG_HOME/stringency/notify.yml`): no file means no notifications and no message about
it; `STRINGENCY_NOTIFY=0` silences everything.

Every word in a message is an engine output: the board's project name, the pipeline's step title,
the hold's reason as `review` prints it, the `plain` sentence, the delivered file names. The link
is the project page's route when `page_url` is configured, else the terminal route.

Reads: holds, runs, steps (through the `Project`), the log. Writes: the log only.
"""

from __future__ import annotations

import json
import os
import smtplib
import subprocess
import sys
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

import yaml

from stringency.clock import now_iso
from stringency.plain import plain_next
from stringency.project import Project
from stringency.runloop import Next

EVENTS = ("hold_opened", "run_completed", "delivered", "run_failed")
KINDS = ("email", "teams_webhook", "command")
LOG_NAME = "notify.log"
TIMEOUT = 5.0

_WORDS = {
    "hold_opened": "the analysis paused",
    "run_completed": "run completed",
    "delivered": "results delivered",
    "run_failed": "run failed",
}


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "stringency" / "notify.yml"


@dataclass
class Config:
    events: list[str]
    channels: list[dict[str, Any]]
    page_url: str | None = None


def load_config(path: Path | None = None) -> Config | None:
    """The per-user file, or None when there is none or it is switched off. A malformed file
    raises ValueError with the reason (the caller logs it and sends nothing)."""
    p = path or config_path()
    if not p.exists():
        return None
    data = yaml.safe_load(p.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{p}: not a mapping")
    if str(data.get("notify", 1)) in ("0", "False", "false", "no", "off"):
        return None
    events = data.get("events", list(EVENTS))
    if not isinstance(events, list) or any(e not in EVENTS for e in events):
        raise ValueError(f"{p}: events must be a list drawn from {', '.join(EVENTS)}")
    channels = data.get("channels") or []
    if not isinstance(channels, list):
        raise ValueError(f"{p}: channels must be a list")
    for ch in channels:
        if not isinstance(ch, dict) or ch.get("kind") not in KINDS:
            raise ValueError(f"{p}: each channel needs kind: {' | '.join(KINDS)}")
    page = data.get("page_url")
    return Config(
        events=[str(e) for e in events],
        channels=channels,
        page_url=str(page) if page else None,
    )


@dataclass
class Message:
    event: str
    key: str  # hold id, run id or delivery id: one message per key per event
    project: str
    subject: str
    text: str
    link: str  # a page URL or the terminal route
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def body(self) -> str:
        return f"{self.text}\n\n{self.link}\n"


# -- what to say ---------------------------------------------------------------------------------


def page_link(page_url: str, path: str) -> str:
    """`page_url` is the landing page with its token (`http://host:port/?t=...`); the message
    links the same server's `/hold/<id>` or `/run/<id>` route, token kept."""
    u = urlsplit(page_url)
    return urlunsplit((u.scheme, u.netloc, path, u.query, ""))


def _link(cfg: Config, root: Path, route: str, terminal: str) -> str:
    return page_link(cfg.page_url, route) if cfg.page_url else terminal


def _hold_messages(project: Project, cfg: Config) -> list[Message]:
    from stringency.review import queue

    out: list[Message] = []
    name = project.root.name
    for h in queue(project):
        step = h["step_id"]
        if h["kind"] == "confirm" or not step:
            title = "the plan"
        else:
            title = project.pipeline.title(step) if project.pipeline.has_step(step) else str(step)
        item = f" (item {h['item_id']})" if h["item_id"] else ""
        reason = str(h["reason"] or "").rstrip(".")
        out.append(
            Message(
                event="hold_opened",
                key=str(h["hold_id"]),
                project=name,
                subject=f"{name}: {_WORDS['hold_opened']}",
                text=f"{name}: the analysis paused at {title}{item}. {h['kind']}: {reason}.",
                link=_link(
                    cfg,
                    project.root,
                    f"/hold/{h['hold_id']}",
                    f"cd {project.root} && stringency review --hold {h['hold_id']}",
                ),
                extra={"hold_id": str(h["hold_id"])},
            )
        )
    return out


def _plain(project: Project, run_id: str, nx: Next) -> str:
    plain = nx.detail.get("plain")
    if isinstance(plain, str) and plain:
        return plain
    rows = project.store.all("SELECT step_id, status FROM steps WHERE run_id = ?", (run_id,))
    statuses = {r["step_id"]: r["status"] for r in rows}
    return plain_next(
        project.pipeline, project.config.roles, nx.kind, nx.step_id, nx.detail, statuses
    )


def messages_for(
    project: Project,
    cfg: Config,
    *,
    run_id: str | None = None,
    nx: Next | None = None,
    delivery: dict[str, Any] | None = None,
) -> list[Message]:
    """Every message the current state and this verb's outcome call for, before de-duplication."""
    name = project.root.name
    out = _hold_messages(project, cfg)
    if nx is not None and run_id:
        run_route = _link(
            cfg,
            project.root,
            f"/run/{run_id}",
            f"cd {project.root} && stringency present --run {run_id}",
        )
        status = project.store.scalar("SELECT status FROM runs WHERE run_id = ?", (run_id,))
        if nx.kind == "completed" and status == "completed":
            plain = _plain(project, run_id, nx)
            out.append(
                Message(
                    "run_completed",
                    run_id,
                    name,
                    f"{name}: {_WORDS['run_completed']}",
                    f"{name}: {plain}",
                    run_route,
                    {"run_id": run_id},
                )
            )
        elif nx.kind == "failed":
            plain = _plain(project, run_id, nx)
            out.append(
                Message(
                    "run_failed",
                    f"{run_id}/{nx.step_id or ''}",
                    name,
                    f"{name}: {_WORDS['run_failed']}",
                    f"{name}: {plain}",
                    run_route,
                    {"run_id": run_id},
                )
            )
    if delivery:
        drun = str(delivery.get("run_id") or run_id or "")
        files = [
            str(f["file"]) if isinstance(f, dict) else str(f) for f in delivery.get("files") or []
        ]
        out.append(
            Message(
                "delivered",
                str(delivery.get("delivery_id") or drun),
                name,
                f"{name}: {_WORDS['delivered']}",
                f"{name}: results delivered: {', '.join(files) or 'no files'}.",
                _link(cfg, project.root, f"/run/{drun}", str(delivery.get("path") or "")),
                {"run_id": drun},
            )
        )
    return [m for m in out if m.event in cfg.events]


# -- the log -------------------------------------------------------------------------------------


def log_path(root: Path) -> Path:
    return Path(root) / ".stringency" / LOG_NAME


def _already_sent(root: Path) -> set[tuple[str, str]]:
    p = log_path(root)
    if not p.exists():
        return set()
    seen: set[tuple[str, str]] = set()
    for line in p.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            seen.add((parts[1], parts[2]))
    return seen


def _log(root: Path, event: str, key: str, channel: str, outcome: str) -> None:
    p = log_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = "\t".join([now_iso(), event, key, channel, outcome.replace("\n", " ")])
    with p.open("a") as fh:
        fh.write(line + "\n")


# -- channels ------------------------------------------------------------------------------------


def _read_credentials(path: str) -> tuple[str, str]:
    p = Path(path).expanduser()
    if p.stat().st_mode & 0o077:
        raise ValueError(f"{p} must be mode 600")
    data = yaml.safe_load(p.read_text())
    if not isinstance(data, dict) or "user" not in data or "password" not in data:
        raise ValueError(f"{p} needs `user` and `password`")
    return str(data["user"]), str(data["password"])


def send_email(ch: dict[str, Any], msg: Message) -> None:
    to = ch.get("to") or []
    to = [to] if isinstance(to, str) else [str(t) for t in to]
    if not to:
        raise ValueError("email channel needs `to`")
    sender = str(ch.get("from") or to[0])
    smtp = ch.get("smtp") or {}
    host = str(smtp.get("host") or "localhost")
    port = int(smtp.get("port") or 25)
    m = EmailMessage()
    m["From"] = sender
    m["To"] = ", ".join(to)
    m["Subject"] = msg.subject
    m["X-Stringency-Event"] = msg.event
    m.set_content(msg.body)
    with smtplib.SMTP(host, port, timeout=TIMEOUT) as s:
        if smtp.get("starttls"):
            s.starttls()
        if ch.get("credentials"):
            user, password = _read_credentials(str(ch["credentials"]))
            s.login(user, password)
        s.send_message(m)


def teams_card(msg: Message) -> dict[str, Any]:
    """One Adaptive Card for a Power Automate "Workflows" webhook (the retired Office 365
    connector format is not used)."""
    body: list[dict[str, Any]] = [
        {"type": "TextBlock", "text": msg.subject, "weight": "Bolder", "wrap": True},
        {"type": "TextBlock", "text": msg.text, "wrap": True},
    ]
    card: dict[str, Any] = {"type": "AdaptiveCard", "version": "1.4", "body": body}
    if msg.link.startswith(("http://", "https://")):
        card["actions"] = [{"type": "Action.OpenUrl", "title": "Open", "url": msg.link}]
    else:
        body.append({"type": "TextBlock", "text": msg.link, "fontType": "Monospace", "wrap": True})
    return {
        "type": "message",
        "attachments": [
            {"contentType": "application/vnd.microsoft.card.adaptive", "content": card}
        ],
    }


def send_teams(ch: dict[str, Any], msg: Message) -> None:
    url = str(ch.get("url") or "")
    if not url.startswith("https://"):
        raise ValueError("teams_webhook channel needs an https `url`")
    data = json.dumps(teams_card(msg)).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 - the person's own webhook URL
        if r.status >= 300:
            raise ValueError(f"webhook answered {r.status}")


def send_command(ch: dict[str, Any], msg: Message) -> None:
    argv = ch.get("argv")
    if not isinstance(argv, list) or not argv:
        raise ValueError("command channel needs `argv`")
    env = {
        **os.environ,
        "STRINGENCY_NOTIFY_EVENT": msg.event,
        "STRINGENCY_NOTIFY_KEY": msg.key,
        "STRINGENCY_NOTIFY_PROJECT": msg.project,
        "STRINGENCY_NOTIFY_SUBJECT": msg.subject,
        "STRINGENCY_NOTIFY_LINK": msg.link,
    }
    r = subprocess.run(
        [str(a) for a in argv],
        input=msg.body,
        text=True,
        capture_output=True,
        timeout=TIMEOUT,
        env=env,
        check=False,
    )
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-1:] or [""]
        raise ValueError(f"exit {r.returncode}: {tail[0]}")


_SENDERS = {"email": send_email, "teams_webhook": send_teams, "command": send_command}


def _channel_name(ch: dict[str, Any]) -> str:
    kind = str(ch.get("kind"))
    if kind == "email":
        to = ch.get("to") or []
        return f"email:{to if isinstance(to, str) else ','.join(map(str, to))}"
    if kind == "command":
        argv = ch.get("argv") or []
        return f"command:{argv[0] if argv else ''}"
    return kind


def send(root: Path, cfg: Config, msg: Message) -> None:
    """Try every channel; log each attempt. Never raises."""
    for ch in cfg.channels:
        name = _channel_name(ch)
        try:
            _SENDERS[str(ch["kind"])](ch, msg)
        except Exception as e:  # noqa: BLE001 - every failure is a log line, never an exit code
            _log(root, msg.event, msg.key, name, f"error: {type(e).__name__}: {e}")
        else:
            _log(root, msg.event, msg.key, name, "ok")


# -- the hook ------------------------------------------------------------------------------------


def notify_after(
    project: Project,
    *,
    run_id: str | None = None,
    nx: Next | None = None,
    delivery: dict[str, Any] | None = None,
) -> list[Message]:
    """Called by a verb after its work, beside `refresh_if_present`. Returns the messages sent
    (for tests). Never raises and never prints to stdout."""
    try:
        if os.environ.get("STRINGENCY_NOTIFY", "1") == "0":
            return []
        try:
            cfg = load_config()
        except (ValueError, yaml.YAMLError, OSError) as e:
            _log(project.root, "config", "-", "-", f"error: {e}")
            return []
        if cfg is None or not cfg.channels:
            return []
        seen = _already_sent(project.root)
        sent: list[Message] = []
        for m in messages_for(project, cfg, run_id=run_id, nx=nx, delivery=delivery):
            if (m.event, m.key) in seen:
                continue
            seen.add((m.event, m.key))
            send(project.root, cfg, m)
            sent.append(m)
        return sent
    except Exception as e:  # noqa: BLE001
        try:
            _log(project.root, "notify", "-", "-", f"error: {type(e).__name__}: {e}")
        except Exception:  # noqa: BLE001
            sys.stderr.write(f"notify: {e}\n")
        return []
