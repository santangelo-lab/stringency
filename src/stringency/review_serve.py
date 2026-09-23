"""`stringency review --serve`: the project page and the localhost form for verdicts (design 7.5
`via: web`, 14.1; `spec/plans/ux-two-audiences.md` section 5.2; `spec/plans/project-page-and-notify.md`
section 3).

The reviewer starts it under their own account, usually through an SSH tunnel
(`scripts/review-page.sh`). It shows every discovered project as the board does, one project's
progress and deliveries, one finished run as `present --run` renders it with its files for
download, and a hold exactly as `review_render.render` prints it, with the verdict form that
records through `record_review(via_override="web")`, so every rule the terminal path applies
(identity, profile, required reason, replicate, correction) applies here too. A random token
printed once at start (or read from `--token-file`) is required on every request; the server
binds to loopback unless told otherwise. `--read-only` refuses every POST (405) for a standing
instance that must not record verdicts under the account that started it.

Every number on a page is an engine output: the board's rows and sentences (`board.row`,
`board.sentence`), `present`'s sections (`present.render_html` over the same rows the markdown
renderer prints), the packet text. No JavaScript, no agent prose.

Reads: what `review_render.render`, `review.queue`, `board.project_entry` and `present` read;
`deliver/<run>/index.json` for the file route. Writes: nothing itself; a POST writes through
`record_review` (reviews, holds, consensus, steps, step_events, artifacts).
"""

from __future__ import annotations

import json
import mimetypes
import secrets
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from jinja2 import Environment, StrictUndefined
from markupsafe import Markup

from stringency.board import COLUMNS, SKIP_DIRS, project_entry, refresh_if_present, row, sentence
from stringency.exit_codes import ConfigError, RefusedError
from stringency.present import Site, present_hold, present_run, render_html
from stringency.project import Project
from stringency.review import _replicates_for, get_hold, record_review
from stringency.review_render import render

DEFAULT_PORT = 8765
DEFAULT_BIND = "127.0.0.1"
REFRESH_SECONDS = 60
READ_ONLY_MESSAGE = (
    "This page is read-only and records no verdict. To record one, start your own page with "
    "scripts/review-page.sh, or run `stringency review --hold <id>` at a terminal in the "
    "project directory."
)


def _candidates(d: Path) -> list[Path]:
    """Subdirectories the board would scan: not `superseded/`, `declarations/` or dot-dirs."""
    return sorted(
        c
        for c in d.iterdir()
        if c.is_dir() and c.name not in SKIP_DIRS and not c.name.startswith(".")
    )


def discover(projects: list[Path], projects_dir: Path | None) -> list[Path]:
    """Project roots: the ones named, plus every child of `projects_dir` to depth two that holds
    a `stringency.yml`, skipping the directories the board skips (`superseded/`, `declarations/`,
    dot-dirs) at both levels. Ordered as given, then by path."""
    roots: list[Path] = [p.resolve() for p in projects]
    if projects_dir is not None:
        base = projects_dir.resolve()
        found: list[Path] = []
        for child in _candidates(base) if base.is_dir() else []:
            if (child / "stringency.yml").exists():
                found.append(child)
                continue
            for grand in _candidates(child):
                if (grand / "stringency.yml").exists():
                    found.append(grand)
        roots += [f for f in found if f not in roots]
    for r in roots:
        if not (r / "stringency.yml").exists():
            raise ConfigError(f"{r} is not a stringency project (no stringency.yml)")
    if not roots:
        raise ConfigError("review --serve needs --project <path> or --projects <dir>")
    return roots


def read_token_file(path: Path) -> str:
    """The token from `--token-file`; created (mode 600) with a fresh token when missing, so a
    standing instance keeps one URL across restarts."""
    p = Path(path).expanduser()
    if p.exists():
        token = p.read_text().strip()
        if not token:
            raise ConfigError(f"{p} is empty")
        return token
    p.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    p.touch(mode=0o600)
    p.write_text(token + "\n")
    return token


_ENV = Environment(undefined=StrictUndefined, autoescape=True)

_STYLE = """
body { font-family: system-ui, sans-serif; max-width: 64em; margin: 2em auto; padding: 0 1em; color: #222; }
h1 { font-size: 1.2em; font-weight: 600; }
h2 { font-size: 1em; font-weight: 600; margin-top: 2em; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 0.3em 0.6em; border-bottom: 1px solid #ddd; vertical-align: top; }
pre { white-space: pre-wrap; word-break: break-word; background: #f6f6f6; padding: 1em; border: 1px solid #ddd; }
p.note { color: #555; font-size: 0.9em; }
p.error { color: #8a1f11; background: #fbe9e7; padding: 0.6em 1em; border: 1px solid #e0b4b4; }
p.crumbs { font-size: 0.9em; }
fieldset { border: 1px solid #ddd; margin: 1em 0; padding: 0.6em 1em; }
label { display: block; margin: 0.3em 0; }
textarea, select { font: inherit; width: 100%; max-width: 40em; }
button { font: inherit; padding: 0.4em 1.2em; }
"""

_HEAD = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{{ title }}</title>{% if refresh %}<meta http-equiv="refresh" content="{{ refresh }}">{% endif %}<style>{{ style }}</style></head>
<body>
"""

_FOOT = """
</body>
</html>
"""

LANDING_HTML = _ENV.from_string(
    _HEAD
    + """<h1>Projects</h1>
<p class="note">Served by stringency review --serve for {{ user }} on {{ host }}{% if read_only %}, read-only{% else %}. A verdict recorded here is recorded as this account's, via web{% endif %}. Read fresh on every load; this page reloads itself every {{ refresh }} seconds.</p>
<h2>Needs you</h2>
{% if holds %}
<table>
<tr><th>project</th><th>step</th><th>kind</th><th>item</th><th>waits on</th><th>open for</th></tr>
{% for r in holds %}
<tr>
<td><a href="{{ r.project_href }}">{{ r.project }}</a></td>
<td><a href="{{ r.href }}">{{ r.step }}</a></td><td>{{ r.kind }}</td><td>{{ r.item }}</td><td>{{ r.waits_on }}</td><td>{{ r.age }}</td>
</tr>
{% endfor %}
</table>
{% else %}
<p>No unresolved holds in {{ n_projects }} project(s).</p>
{% endif %}
<h2>Board</h2>
<table>
<tr>{% for c in columns %}<th>{{ c }}</th>{% endfor %}</tr>
{% for b in board %}
<tr>{% for c in columns %}<td>{% if loop.first %}<a href="{{ b.href }}">{{ b.cells[c] }}</a>{% else %}{{ b.cells[c] }}{% endif %}</td>{% endfor %}</tr>
{% endfor %}
</table>
<h2>In words</h2>
<ul>
{% for b in board %}<li><a href="{{ b.href }}">{{ b.name }}</a>: {{ b.sentence }}</li>
{% endfor %}
</ul>
"""
    + _FOOT
)

PROJECT_HTML = _ENV.from_string(
    _HEAD
    + """<p class="crumbs"><a href="{{ list_href }}">All projects</a></p>
<h1>{{ name }}</h1>
<p>{{ sentence }}</p>
{% if error %}<p class="error">{{ error }}</p>{% else %}
<h2>Steps</h2>
{% if steps %}
<table>
<tr><th>step</th><th>status</th></tr>
{% for s in steps %}<tr><td>{{ s.title }}</td><td>{{ s.status }}</td></tr>
{% endfor %}
</table>
{% else %}<p>No run has started.</p>{% endif %}
<h2>Needs you</h2>
{% if holds %}
<table>
<tr><th>step</th><th>kind</th><th>item</th><th>waits on</th><th>open for</th></tr>
{% for r in holds %}
<tr><td><a href="{{ r.href }}">{{ r.step }}</a></td><td>{{ r.kind }}</td><td>{{ r.item }}</td><td>{{ r.waits_on }}</td><td>{{ r.age }}</td></tr>
{% endfor %}
</table>
{% else %}<p>Nothing waits on a person. The plan is {{ confirm }}.</p>{% endif %}
<h2>Delivered</h2>
{% if deliveries %}
<table>
<tr><th>when</th><th>results</th><th>files</th></tr>
{% for d in deliveries %}
<tr><td>{{ d.when }}</td><td><a href="{{ d.href }}">open</a></td><td>{{ d.files | join(", ") }}</td></tr>
{% endfor %}
</table>
{% else %}<p>Nothing delivered yet.</p>{% endif %}
{% endif %}
"""
    + _FOOT
)

RUN_HTML = _ENV.from_string(
    _HEAD
    + """<p class="crumbs"><a href="{{ list_href }}">All projects</a> / <a href="{{ project_href }}">{{ name }}</a></p>
<h1>{{ name }}: results</h1>
<p>{{ progress }}</p>
{{ sections }}
{% if summary %}<h2>Summary</h2>
<pre>{{ summary }}</pre>{% endif %}
<h2>Files</h2>
{% if files %}
<table>
<tr><th>file</th><th>kind</th><th>from step</th></tr>
{% for f in files %}<tr><td><a href="{{ f.href }}">{{ f.name }}</a></td><td>{{ f.kind }}</td><td>{{ f.step }}</td></tr>
{% endfor %}
</table>
{% else %}<p>Not delivered yet; nothing to download.</p>{% endif %}
"""
    + _FOOT
)

HOLD_HTML = _ENV.from_string(
    _HEAD
    + """<p class="crumbs"><a href="{{ list_href }}">All projects</a> / <a href="{{ project_href }}">{{ project }}</a></p>
<h1>Hold {{ hold_id }} ({{ kind }}){% if step_title %} on {{ step_title }}{% endif %}{% if item_id %}, item {{ item_id }}{% endif %}</h1>
<p class="note">Project {{ project }}. What follows is what stringency review prints at a terminal; the form
records the same verdicts by the same rules.</p>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
{{ view_sections }}
<pre>{{ text }}</pre>
{% if resolved %}
<p>This hold was resolved by review {{ resolved }}.</p>
{% elif read_only %}
<p class="note">{{ read_only_message }}</p>
{% else %}
<form method="post" action="{{ post_href }}">
<input type="hidden" name="t" value="{{ token }}">
<fieldset>
<legend>Verdict</legend>
{% for v in verdicts %}
<label><input type="radio" name="verdict" value="{{ v.verdict }}"{% if v.verdict == chosen %} checked{% endif %}> <strong>{{ v.verdict }}</strong>: {{ v.effect }}</label>
{% endfor %}
</fieldset>
{% if replicates %}
<fieldset>
<legend>Replicate (accept on an item hold takes one replicate's call)</legend>
<select name="replicate">
<option value="">choose</option>
{% for r in replicates %}
<option value="{{ r.replicate }}">replicate {{ r.replicate }}: {{ r.label if r.label is not none else 'abstain' }} ({{ r.confidence }})</option>
{% endfor %}
</select>
</fieldset>
{% endif %}
{% if vocabulary %}
<fieldset>
<legend>Correction (override only): a label from the module's vocabulary</legend>
<select name="label">
<option value="">choose</option>
{% for lab in vocabulary %}
<option value="{{ lab }}">{{ lab }}</option>
{% endfor %}
</select>
</fieldset>
{% endif %}
<fieldset>
<legend>Reason, in your own words (required for accept on a flag, reject, override)</legend>
<textarea name="reason" rows="4">{{ reason }}</textarea>
</fieldset>
<button type="submit">Record verdict</button>
</form>
{% endif %}
"""
    + _FOOT
)

DONE_HTML = _ENV.from_string(
    _HEAD
    + """<h1>Recorded</h1>
<p>Review {{ review_id }}: {{ verdict }} on hold {{ hold_id }} via {{ via }}{% if step_status %}; step {{ step_status }}, run {{ run_status }}{% endif %}.</p>
<p><a href="{{ project_href }}">Back to the project</a> · <a href="{{ list_href }}">All projects</a></p>
"""
    + _FOOT
)

ERROR_HTML = _ENV.from_string(
    _HEAD
    + """<h1>{{ title }}</h1>
<p class="error">{{ message }}</p>
{% if list_href %}<p><a href="{{ list_href }}">All projects</a></p>{% endif %}
"""
    + _FOOT
)


def _age(created: str | None) -> str:
    if not created:
        return ""
    try:
        then = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        return ""
    delta = datetime.now(UTC) - then
    hours = int(delta.total_seconds() // 3600)
    if hours < 1:
        return f"{int(delta.total_seconds() // 60)} min"
    if hours < 48:
        return f"{hours} h"
    return f"{hours // 24} d"


_OPEN_HOLDS_SQL = (
    "SELECT * FROM holds WHERE resolved_by_review IS NULL AND resolved_via IS NULL "
    "ORDER BY run_id IS NOT NULL, created, rowid"
)

_KIND_TYPES = {
    "json": "application/json",
    "prose": "text/markdown; charset=utf-8",
    "text": "text/plain; charset=utf-8",
}


def served_files(deliver_dir: Path) -> dict[str, tuple[str, str, str]]:
    """The names `index.json` lists, each with its content type, recorded kind and step: the
    delivered files, their sidecars, and the three reports. Anything else is not served."""
    idx = json.loads((deliver_dir / "index.json").read_text())
    out: dict[str, tuple[str, str, str]] = {}
    for f in idx.get("files", []):
        name = str(f["file"])
        kind = str(f.get("kind") or "")
        out[name] = (_content_type(name, kind), kind, str(f.get("step_id") or ""))
        if f.get("sidecar"):
            out[str(f["sidecar"])] = ("application/json", "sidecar", str(f.get("step_id") or ""))
    for key in ("coverage", "methods", "summary"):
        entry = idx.get(key)
        if isinstance(entry, dict) and entry.get("file"):
            out[str(entry["file"])] = ("text/markdown; charset=utf-8", key, "")
    return out


def _content_type(name: str, kind: str) -> str:
    if name.endswith((".tsv", ".tab")):
        return "text/tab-separated-values; charset=utf-8"
    if name.endswith(".csv"):
        return "text/csv; charset=utf-8"
    if kind in _KIND_TYPES:
        return _KIND_TYPES[kind]
    guessed, _ = mimetypes.guess_type(name)
    return guessed or "application/octet-stream"


@dataclass
class ServerState:
    roots: list[Path]
    token: str
    user: str
    host: str
    read_only: bool = False


class ReviewHandler(BaseHTTPRequestHandler):
    """One request at a time per thread; each request opens its own `Site` or `Project`."""

    server: ReviewHTTPServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        sys.stderr.write("review --serve: " + (format % args) + "\n")

    # -- helpers ------------------------------------------------------------------------------

    @property
    def state(self) -> ServerState:
        return self.server.state

    def _send(self, status: HTTPStatus, body: str) -> None:
        self._send_bytes(status, body.encode("utf-8"), "text/html; charset=utf-8")

    def _send_bytes(
        self, status: HTTPStatus, data: bytes, content_type: str, filename: str | None = None
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if filename is not None:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _error(self, status: HTTPStatus, message: str, *, with_link: bool = True) -> None:
        self._send(
            status,
            ERROR_HTML.render(
                title=f"{status.value} {status.phrase}",
                message=message,
                list_href=self._list_href() if with_link else "",
                refresh=None,
                style=_STYLE,
            ),
        )

    def _token_ok(self, params: dict[str, list[str]]) -> bool:
        given = params.get("t", [""])[0]
        return bool(given) and secrets.compare_digest(given, self.state.token)

    def _href(self, path: str) -> str:
        return f"{path}?t={self.state.token}"

    def _list_href(self) -> str:
        return self._href("/")

    def _root(self, index: int) -> Path:
        if index < 0 or index >= len(self.state.roots):
            raise ConfigError(f"no project {index}")
        return self.state.roots[index]

    def _project(self, index: int) -> Project:
        return Project.load(self._root(index))

    def _site(self, index: int) -> Site:
        return Site.load(self._root(index))

    def _hold_rows(self, index: int, site: Site) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for h in site.store.all(_OPEN_HOLDS_SQL):
            step = h["step_id"]
            title = (
                site.pipeline.title(step)
                if step and site.pipeline.has_step(step)
                else (step or "the plan")
            )
            who = (
                site.config.roles.reviewer
                if h["waits_on_role"] == "reviewer"
                else site.config.roles.owner
            )
            rows.append(
                {
                    "project": site.root.name,
                    "project_href": self._href(f"/p/{index}"),
                    "step": title,
                    "kind": h["kind"],
                    "item": h["item_id"] or "",
                    "waits_on": f"{h['waits_on_role']} {who}",
                    "age": _age(h["created"]),
                    "href": self._href(f"/p/{index}/hold/{h['hold_id']}"),
                }
            )
        return rows

    # -- routes -------------------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        params = parse_qs(url.query)
        if not self._token_ok(params):
            self._error(
                HTTPStatus.FORBIDDEN,
                "this page needs the token printed when the server started",
                with_link=False,
            )
            return
        parts = [unquote(p) for p in url.path.split("/") if p]
        try:
            if not parts:
                self._send(HTTPStatus.OK, self._render_landing())
            elif len(parts) == 2 and parts[0] in ("hold", "run"):
                self._redirect_by_id(parts[0], parts[1])
            elif parts[0] == "p" and len(parts) == 2:
                self._send(HTTPStatus.OK, self._render_project(int(parts[1])))
            elif parts[0] == "p" and len(parts) == 4 and parts[2] == "hold":
                index = int(parts[1])
                project = self._project(index)
                h = get_hold(project, parts[3])
                self._send(HTTPStatus.OK, self._render_hold(index, project, h))
            elif parts[0] == "p" and len(parts) == 4 and parts[2] == "run":
                self._send(HTTPStatus.OK, self._render_run(int(parts[1]), parts[3]))
            elif parts[0] == "p" and len(parts) == 5 and parts[2] == "file":
                self._send_file(int(parts[1]), parts[3], parts[4])
            else:
                self._error(HTTPStatus.NOT_FOUND, "no such page")
        except (ConfigError, ValueError) as e:
            self._error(HTTPStatus.NOT_FOUND, str(e))
        except Exception as e:  # noqa: BLE001 - one request's failure is one error page
            self.log_message("error: %s: %s", type(e).__name__, e)
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")

    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        if not self._token_ok(form) and not self._token_ok(parse_qs(url.query)):
            self._error(
                HTTPStatus.FORBIDDEN,
                "this page needs the token printed when the server started",
                with_link=False,
            )
            return
        if self.state.read_only:
            self._error(HTTPStatus.METHOD_NOT_ALLOWED, READ_ONLY_MESSAGE)
            return
        parts = [unquote(p) for p in url.path.split("/") if p]
        if not (len(parts) == 4 and parts[0] == "p" and parts[2] == "hold"):
            self._error(HTTPStatus.NOT_FOUND, "no such page")
            return
        try:
            index = int(parts[1])
            project = self._project(index)
            h = get_hold(project, parts[3])
        except (ConfigError, ValueError) as e:
            self._error(HTTPStatus.NOT_FOUND, str(e))
            return
        verdict = form.get("verdict", [""])[0]
        reason = form.get("reason", [""])[0].strip() or None
        rep_raw = form.get("replicate", [""])[0].strip()
        replicate = int(rep_raw) if rep_raw else None
        label = form.get("label", [""])[0].strip()
        correction = {"label": label} if verdict == "override" and label else None
        try:
            if not verdict:
                raise ConfigError("choose a verdict")
            result = record_review(
                project,
                h["hold_id"],
                verdict,
                reason=reason,
                correction=correction,
                replicate=replicate,
                via_override="web",
            )
        except RefusedError as e:
            self._error(HTTPStatus.FORBIDDEN, str(e))
            return
        except ConfigError as e:
            self._send(
                HTTPStatus.BAD_REQUEST,
                self._render_hold(
                    index, project, h, error=str(e), chosen=verdict, reason=reason or ""
                ),
            )
            return
        refresh_if_present(project.root)
        self._send(
            HTTPStatus.OK,
            DONE_HTML.render(
                title="stringency review recorded",
                review_id=result.review_id,
                verdict=result.verdict,
                hold_id=result.hold_id,
                via=result.via,
                step_status=result.step_status,
                run_status=result.run_status,
                project_href=self._href(f"/p/{index}"),
                list_href=self._list_href(),
                refresh=None,
                style=_STYLE,
            ),
        )

    def _redirect_by_id(self, what: str, ident: str) -> None:
        """`/hold/<id>` and `/run/<id>` (the routes a notification links to) find the project
        that holds the id and redirect to its page."""
        table, column = ("holds", "hold_id") if what == "hold" else ("runs", "run_id")
        for i, root in enumerate(self.state.roots):
            try:
                site = Site.load(root)
            except Exception:  # noqa: BLE001 - an unreadable project is skipped, not fatal
                continue
            try:
                found = site.store.one(f"SELECT 1 FROM {table} WHERE {column} = ?", (ident,))
            finally:
                site.store.close()
            if found is not None:
                self._redirect(self._href(f"/p/{i}/{what}/{ident}"))
                return
        raise ConfigError(f"no {what} {ident} in {len(self.state.roots)} project(s)")

    # -- rendering ----------------------------------------------------------------------------

    def _render_landing(self) -> str:
        holds: list[dict[str, str]] = []
        board: list[dict[str, Any]] = []
        for i, root in enumerate(self.state.roots):
            entry = project_entry(root)
            board.append(
                {
                    "name": root.name,
                    "href": self._href(f"/p/{i}"),
                    "cells": row(entry),
                    "sentence": sentence(entry),
                }
            )
            if "error" in entry:
                continue
            site = Site.load(root)
            try:
                holds += self._hold_rows(i, site)
            finally:
                site.store.close()
        return LANDING_HTML.render(
            title="stringency projects",
            holds=holds,
            board=board,
            columns=list(COLUMNS),
            n_projects=len(self.state.roots),
            user=self.state.user,
            host=self.state.host,
            read_only=self.state.read_only,
            refresh=REFRESH_SECONDS,
            style=_STYLE,
        )

    def _render_project(self, index: int) -> str:
        root = self._root(index)
        entry = project_entry(root)
        common = {
            "title": f"stringency: {root.name}",
            "name": root.name,
            "sentence": sentence(entry),
            "list_href": self._list_href(),
            "refresh": REFRESH_SECONDS,
            "style": _STYLE,
        }
        if "error" in entry:
            return PROJECT_HTML.render(
                error=entry["error"], steps=[], holds=[], deliveries=[], confirm="", **common
            )
        site = Site.load(root)
        try:
            steps: list[dict[str, str]] = []
            if entry.get("run"):
                statuses = site.step_statuses(entry["run"]["run_id"])
                steps = [
                    {
                        "title": site.pipeline.title(s),
                        "status": statuses.get(s, "pending").replace("_", " "),
                    }
                    for s in site.pipeline.order()
                ]
            holds = self._hold_rows(index, site)
            deliveries: list[dict[str, Any]] = []
            for d in site.store.all(
                "SELECT run_id, path, ts FROM deliveries ORDER BY ts DESC, rowid DESC"
            ):
                files: list[str] = []
                try:
                    files = list(served_files(Path(d["path"])))
                    files = [f for f in files if not f.endswith(".stringency.json")]
                except (OSError, ValueError, KeyError):
                    files = []
                deliveries.append(
                    {
                        "when": d["ts"],
                        "href": self._href(f"/p/{index}/run/{d['run_id']}"),
                        "files": files,
                    }
                )
        finally:
            site.store.close()
        return PROJECT_HTML.render(
            error=None,
            steps=steps,
            holds=holds,
            deliveries=deliveries,
            confirm=entry.get("confirm", ""),
            **common,
        )

    def _render_run(self, index: int, run_id: str) -> str:
        site = self._site(index)
        try:
            payload = present_run(site, run_id)
            d = site.store.one(
                "SELECT path FROM deliveries WHERE run_id = ? ORDER BY ts DESC, rowid DESC LIMIT 1",
                (run_id,),
            )
        finally:
            site.store.close()
        summary = ""
        files: list[dict[str, str]] = []
        if d is not None and (Path(d["path"]) / "index.json").exists():
            ddir = Path(d["path"])
            if (ddir / "summary.md").exists():
                summary = (ddir / "summary.md").read_text()
            for name, (_ctype, kind, step) in served_files(ddir).items():
                if kind == "sidecar":
                    continue
                files.append(
                    {
                        "name": name,
                        "kind": kind,
                        "step": site.pipeline.title(step) if site.pipeline.has_step(step) else "",
                        "href": self._href(f"/p/{index}/file/{run_id}/{name}"),
                    }
                )
        return RUN_HTML.render(
            title=f"stringency: {site.root.name} results",
            name=site.root.name,
            progress=payload["progress"],
            sections=Markup(render_html(payload)),  # noqa: S704 - autoescaped template output
            summary=summary,
            files=files,
            list_href=self._list_href(),
            project_href=self._href(f"/p/{index}"),
            refresh=None,
            style=_STYLE,
        )

    def _send_file(self, index: int, run_id: str, name: str) -> None:
        """One delivered file, only when `index.json` lists its name; never a path."""
        if "/" in name or "\\" in name or name in ("", ".", "..") or name.startswith("."):
            raise ConfigError("no such file")
        site = self._site(index)
        try:
            d = site.store.one(
                "SELECT path FROM deliveries WHERE run_id = ? ORDER BY ts DESC, rowid DESC LIMIT 1",
                (run_id,),
            )
        finally:
            site.store.close()
        if d is None or not (Path(d["path"]) / "index.json").exists():
            raise ConfigError(f"run {run_id} has no delivery")
        ddir = Path(d["path"])
        listed = served_files(ddir)
        if name not in listed:
            raise ConfigError(f"{name} is not a delivered file of run {run_id}")
        target = ddir / name
        if not target.is_file():
            raise ConfigError(f"{name} is not a file")
        self._send_bytes(HTTPStatus.OK, target.read_bytes(), listed[name][0], filename=name)

    def _render_hold(
        self,
        index: int,
        project: Project,
        h: Any,
        *,
        error: str | None = None,
        chosen: str = "",
        reason: str = "",
    ) -> str:
        view = render(project, h)
        is_item = h["item_id"] is not None
        replicates = _replicates_for(project, h) if is_item else []
        vocabulary: list[str] = []
        if is_item and h["bound_module_version"]:
            module = project.modules.get(h["bound_module_version"])
            if module is not None and module.manifest.vocabulary:
                vocabulary = list(project.plugin.vocabulary(module.manifest.vocabulary) or ())
        step = h["step_id"]
        step_title = (
            project.pipeline.title(step) if step and project.pipeline.has_step(step) else step
        )
        view_sections = ""
        if h["kind"] != "confirm":  # the confirm packet is the echo-back already
            site = Site.load(project.root)
            try:
                hp = present_hold(site, h["hold_id"])
            finally:
                site.store.close()
            if hp["sections"]:
                view_sections = render_html(hp)
        return HOLD_HTML.render(
            title=f"stringency hold {h['hold_id']}",
            hold_id=h["hold_id"],
            kind=h["kind"],
            step_title=step_title,
            item_id=h["item_id"],
            project=project.root.name,
            text=view.text,
            view_sections=Markup(view_sections),  # noqa: S704 - autoescaped template output
            verdicts=view.verdicts,
            replicates=replicates,
            vocabulary=vocabulary,
            chosen=chosen,
            reason=reason,
            error=error,
            resolved=h["resolved_by_review"],
            read_only=self.state.read_only,
            read_only_message=READ_ONLY_MESSAGE,
            token=self.state.token,
            list_href=self._list_href(),
            project_href=self._href(f"/p/{index}"),
            post_href=f"/p/{index}/hold/{h['hold_id']}",
            refresh=None,
            style=_STYLE,
        )


class ReviewHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], state: ServerState) -> None:
        super().__init__(address, ReviewHandler)
        self.state = state


def make_server(
    roots: list[Path],
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    token: str | None = None,
    read_only: bool = False,
) -> ReviewHTTPServer:
    """Build the server without serving (tests bind port 0). Identity is the OS user running it."""
    import socket

    from stringency.review import current_user

    state = ServerState(
        roots=list(roots),
        token=token or secrets.token_urlsafe(24),
        user=current_user(),
        host=socket.gethostname(),
        read_only=read_only,
    )
    return ReviewHTTPServer((bind, port), state)


def serve(
    projects: list[Path],
    projects_dir: Path | None,
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    read_only: bool = False,
    token_file: Path | None = None,
) -> None:
    """Print the URL with its token once, then serve until interrupted."""
    roots = discover(projects, projects_dir)
    token = read_token_file(token_file) if token_file is not None else None
    srv = make_server(roots, bind=bind, port=port, token=token, read_only=read_only)
    host, actual = str(srv.server_address[0]), int(srv.server_address[1])
    mode = "read-only, no verdicts" if read_only else "verdicts recorded here carry via: web"
    print(
        f"stringency review --serve: {len(roots)} project(s) as {srv.state.user}; "
        f"open http://{host}:{actual}/?t={srv.state.token}",
        flush=True,
    )
    print(f"{mode}; stop with Ctrl-C", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
