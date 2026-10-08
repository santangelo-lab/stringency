"""`stringency review --serve`: the console (design 7.5 `via: web`, 14.1;
`spec/plans/console-and-fleet-plan.md`; before it `spec/archive/project-page-and-notify.md`).

The reviewer starts it under their own account, usually through an SSH tunnel
(`scripts/review-page.sh`) or as a standing `systemd --user` service
(`scripts/stringency-console.service`). It shows every discovered project as the board does, one
project's progress and deliveries, one finished run as `present --run` renders it with its files
for download, and a hold exactly as `review_render.render` prints it, with the verdict form that
records through `record_review(via_override="web")`, so every rule the terminal path applies
(identity, profile, required reason, replicate, correction) applies here too. A random token
printed once at start (or read from `--token-file`) is required on every request: in `?t=` on the
first visit, after which the server sets it as a cookie so links, images and the event stream
carry none. The server binds to loopback unless told otherwise. `--read-only` refuses every POST
(405) for a standing instance that must not record verdicts under the account that started it.

Routes are keyed by the trace's own ids (`/project/<project_id>`, `/hold/<hold_id>`,
`/run/<run_id>`, `/file/<run_id>/<name>`), since the set of projects changes while the console
runs; the positional `/p/<i>/...` routes of engine 0.2.6 redirect to them. Several `--projects`
directories may be given; they are rescanned every thirty seconds.

Every number on a page is an engine output: the board's rows and sentences (`board.row`,
`board.sentence`), `present`'s sections (`present.render_html` over the same rows the markdown
renderer prints), the packet text. No agent prose.

Reads: what `review_render.render`, `review.queue`, `board.project_entry` and `present` read;
`deliver/<run>/index.json` for the file route. Writes: nothing itself; a POST writes through
`record_review` (reviews, holds, consensus, steps, step_events, artifacts).
"""

from __future__ import annotations

import json
import mimetypes
import queue
import secrets
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from jinja2 import Environment, StrictUndefined
from markupsafe import Markup

from stringency.board import COLUMNS, project_entry, refresh_if_present, row, sentence
from stringency.console import (
    Registry,
    Watcher,
    ask_of,
    card_title,
    discover,
    driver,
    group_cards,
    hold_context,
    references,
    timeline,
)
from stringency.exit_codes import ConfigError, RefusedError
from stringency.present import Site, load_skill, present_hold, present_run, render_html
from stringency.project import Project
from stringency.review import _replicates_for, get_hold, record_review
from stringency.review_render import render
from stringency.when import skip_reason

__all__ = ["discover", "make_server", "read_token_file", "serve"]

DEFAULT_PORT = 8765
DEFAULT_BIND = "127.0.0.1"
REFRESH_SECONDS = 60
COOKIE_PREFIX = "stringency_console_"
READ_ONLY_MESSAGE = (
    "This page is read-only and records no verdict. To record one, start your own page with "
    "scripts/review-page.sh, or run `stringency review --hold <id>` at a terminal in the "
    "project directory."
)


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
h3 { font-size: 0.95em; font-weight: 600; margin: 1.2em 0 0.4em; }
.fork { margin-left: 1.5em; }
.stale { color: #8a5a00; }
tr.focus td { outline: 2px solid #2f5d9e; }
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
<head><meta charset="utf-8"><title>{{ title }}</title>{% if refresh %}<meta http-equiv="refresh" content="{{ refresh }}">{% endif %}<style>{{ style }}</style><script src="/static/console.js" defer></script></head>
<body>
"""
STATIC_DIR = Path(__file__).with_name("static")
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'unsafe-inline'; img-src 'self'; "
    "connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
)

_FOOT = """
</body>
</html>
"""

LANDING_HTML = _ENV.from_string(
    _HEAD
    + """<h1>Projects</h1>
<p class="note">Served by stringency review --serve for {{ user }} on {{ host }}{% if read_only %}, read-only{% else %}. A verdict recorded here is recorded as this account's, via web{% endif %}. Read fresh on every load; this page reloads itself every {{ refresh }} seconds.</p>
<section data-live="needs">
<h2>Needs you{% if n_holds %} ({{ n_holds }}){% endif %}</h2>
{% if n_holds %}
{% for g in groups if g.cards %}
<h3>{{ g.heading }}</h3>
<table>
<tr><th>project</th><th>what</th><th>step</th><th>kind</th><th>item</th><th>waits on</th><th>open for</th></tr>
{% for c in g.cards %}
<tr data-card="{{ c.hold_id }}"><td><a href="{{ c.project_href }}">{{ c.project }}</a></td><td><a href="{{ c.href }}" data-open>{{ c.title }}</a></td><td>{{ c.step }}</td><td>{{ c.kind }}</td><td>{{ c.item }}</td><td>{{ c.waits_on }}</td><td>{{ c.age }}</td></tr>
{% endfor %}
</table>
{% endfor %}
{% else %}
<p>No unresolved holds in {{ n_projects }} project(s).</p>
{% endif %}
</section>
<section data-live="board">
<h2>Board</h2>
<table>
<tr>{% for c in columns %}<th>{{ c }}</th>{% endfor %}<th>for</th><th>elsewhere</th><th>driver</th><th>last call</th></tr>
{% for b in board %}
<tr>{% for c in columns %}<td>{% if loop.first and b.href %}<a href="{{ b.href }}">{{ b.cells[c] }}</a>{% else %}{{ b.cells[c] }}{% endif %}</td>{% endfor %}<td>{{ b.driver.elapsed }}</td><td>{{ b.driver.elsewhere }}</td><td>{{ b.driver.who }}</td><td>{{ b.driver.last_call_age }}{% if b.driver.stale %} <strong class="stale">stale</strong>{% endif %}</td></tr>
{% endfor %}
</table>
<p class="note">"for": how long the current step has been in its state; "elsewhere": the median time the same step took where it completed, in the projects shown; "stale": no engine call for longer than fifteen minutes and twice that time while the step is the engine's or the operator's.</p>
<h2>In words</h2>
<ul>
{% for b in board %}<li>{% if b.href %}<a href="{{ b.href }}">{{ b.name }}</a>{% else %}{{ b.name }}{% endif %}: {{ b.sentence }}</li>
{% endfor %}
</ul>
</section>
"""
    + _FOOT
)

PROJECT_HTML = _ENV.from_string(
    _HEAD
    + """<p class="crumbs"><a href="{{ list_href }}">All projects</a></p>
<h1>{{ name }}</h1>
<section data-live="project">
<p>{{ sentence }}</p>
{% if error %}<p class="error">{{ error }}</p>{% else %}
{% if driver %}<p class="note">Driver: {{ driver.who }}. Last engine call {{ driver.last_call_age }} ago{% if driver.stale %}, <strong class="stale">stale</strong>{% endif %}.{% if driver.step %} '{{ driver.step }}' has been {{ driver.status }} for {{ driver.elapsed }}{% if driver.elsewhere %}; elsewhere it took {{ driver.elsewhere }}{% endif %}.{% endif %}</p>{% endif %}
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
<tr><th>what</th><th>step</th><th>kind</th><th>item</th><th>waits on</th><th>open for</th></tr>
{% for r in holds %}
<tr><td><a href="{{ r.href }}">{{ r.title }}</a></td><td>{{ r.step }}</td><td>{{ r.kind }}</td><td>{{ r.item }}</td><td>{{ r.waits_on }}</td><td>{{ r.age }}</td></tr>
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
<h2>Timeline</h2>
{% for r in timeline %}
<h3{% if r.fork %} class="fork"{% endif %}>{{ r.label }}, {{ r.status }}{% if r.fork %} (a fork){% endif %}</h3>
<ul{% if r.fork %} class="fork"{% endif %}>
{% for e in r.events %}<li>{{ e.when }}: {{ e.text }}</li>
{% endfor %}
</ul>
{% endfor %}
{% endif %}
</section>
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
<form method="post" action="{{ post_href }}" data-verdict>
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
<legend>Reason, in your own words (required for accept on a flag, reject, override). The operator reads it when it resumes: if the verdict needs a next step, say it here.</legend>
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


_NO_DRIVER: dict[str, Any] = {
    "who": "",
    "elapsed": "",
    "elsewhere": "",
    "last_call_age": "",
    "stale": False,
    "step": None,
    "status": None,
}


@dataclass
class ServerState:
    registry: Registry
    token: str
    user: str
    host: str
    read_only: bool = False

    @property
    def roots(self) -> list[Path]:
        self.registry.refresh()
        return self.registry.roots


class ReviewHandler(BaseHTTPRequestHandler):
    """One request at a time per thread; each request opens its own `Site` or `Project`."""

    server: ReviewHTTPServer
    _issue_cookie: bool = False

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        sys.stderr.write("review --serve: " + (format % args) + "\n")

    # -- helpers ------------------------------------------------------------------------------

    @property
    def state(self) -> ServerState:
        return self.server.state

    @property
    def cookie_name(self) -> str:
        """Per port, since the browser ignores the port when it matches cookies and a read-only
        instance may run beside this one on the same host."""
        return f"{COOKIE_PREFIX}{self.server.server_address[1]}"

    def _send(self, status: HTTPStatus, body: str) -> None:
        self._send_bytes(status, body.encode("utf-8"), "text/html; charset=utf-8", csp=True)

    def _send_json(self, payload: Any) -> None:
        self._send_bytes(
            HTTPStatus.OK, json.dumps(payload, indent=1).encode("utf-8"), "application/json"
        )

    def _send_bytes(
        self,
        status: HTTPStatus,
        data: bytes,
        content_type: str,
        filename: str | None = None,
        *,
        csp: bool = False,
        cache: str = "no-store",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        if csp:
            self.send_header("Content-Security-Policy", CSP)
        if filename is not None:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self._cookie_header()
        self.end_headers()
        self.wfile.write(data)

    def _cookie_header(self) -> None:
        if self._issue_cookie:
            self.send_header(
                "Set-Cookie",
                f"{self.cookie_name}={self.state.token}; HttpOnly; SameSite=Strict; Path=/",
            )
            self._issue_cookie = False

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self._cookie_header()
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
        """The token in `?t=` or a form field, or the cookie this server set on an earlier
        tokened request. A query token marks the response to carry the cookie."""
        given = params.get("t", [""])[0]
        if given and secrets.compare_digest(given, self.state.token):
            self._issue_cookie = True
            return True
        raw = self.headers.get("Cookie")
        if raw:
            jar: SimpleCookie = SimpleCookie()
            try:
                jar.load(raw)
            except Exception:  # noqa: BLE001 - a malformed cookie is no cookie
                return False
            morsel = jar.get(self.cookie_name)
            if morsel is not None and secrets.compare_digest(morsel.value, self.state.token):
                return True
        return False

    def _href(self, path: str) -> str:
        return path

    def _list_href(self) -> str:
        return "/"

    def _project_href(self, root: Path) -> str:
        pid = self.state.registry.id_of(root)
        return f"/project/{pid}" if pid else ""

    def _cards(self, root: Path, site: Site) -> list[dict[str, Any]]:
        """The open holds of one project as inbox cards: the engine's group (which question the
        hold asks) and the method's title when its delivery skill gives one."""
        skill, _note = load_skill(site)
        cards: list[dict[str, Any]] = []
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
            ctx = hold_context(h)
            group = ask_of(h, ctx)
            cards.append(
                {
                    "hold_id": h["hold_id"],
                    "created": h["created"] or "",
                    "group": group,
                    "title": card_title(h, ctx, group, title, skill),
                    "project": site.root.name,
                    "project_href": self._project_href(root),
                    "step": title,
                    "kind": h["kind"],
                    "item": h["item_id"] or "",
                    "waits_on": f"{h['waits_on_role']} {who}",
                    "age": _age(h["created"]),
                    "href": f"/hold/{h['hold_id']}",
                }
            )
        return cards

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
        reg = self.state.registry
        try:
            if not parts:
                self._send(HTTPStatus.OK, self._render_landing())
            elif parts == ["static", "console.js"]:
                self._send_bytes(
                    HTTPStatus.OK,
                    (STATIC_DIR / "console.js").read_bytes(),
                    "text/javascript; charset=utf-8",
                    cache="private, max-age=300",
                )
            elif parts == ["events"]:
                self._stream_events()
            elif parts[0] == "api":
                self._send_json(self._api(parts[1:]))
            elif parts[0] == "project" and len(parts) == 2:
                self._send(HTTPStatus.OK, self._render_project(reg.root_of(parts[1])))
            elif parts[0] == "hold" and len(parts) == 2:
                _pid, root = reg.owner_of("hold", parts[1])
                project = Project.load(root)
                self._send(HTTPStatus.OK, self._render_hold(project, get_hold(project, parts[1])))
            elif parts[0] == "run" and len(parts) == 2:
                _pid, root = reg.owner_of("run", parts[1])
                self._send(HTTPStatus.OK, self._render_run(root, parts[1]))
            elif parts[0] == "file" and len(parts) == 3:
                _pid, root = reg.owner_of("run", parts[1])
                self._send_file(root, parts[1], parts[2])
            elif parts[0] == "p":
                self._redirect_legacy(parts, params)
            else:
                self._error(HTTPStatus.NOT_FOUND, "no such page")
        except (ConfigError, ValueError) as e:
            self._error(HTTPStatus.NOT_FOUND, str(e))
        except Exception as e:  # noqa: BLE001 - one request's failure is one error page
            self.log_message("error: %s: %s", type(e).__name__, e)
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")

    def _redirect_legacy(self, parts: list[str], params: dict[str, list[str]]) -> None:
        """The `/p/<i>/...` routes of engine 0.2.6 (bookmarks, old notification links): the
        project at that position today, redirected to its id route. A query token is carried
        over, since a client following the redirect may not keep the cookie."""
        reg = self.state.registry
        suffix = f"?t={params['t'][0]}" if params.get("t") else ""
        if len(parts) == 2:
            self._redirect((self._project_href(reg.root_at(int(parts[1]))) or "/") + suffix)
        elif len(parts) == 4 and parts[2] in ("hold", "run"):
            reg.root_at(int(parts[1]))
            self._redirect(f"/{parts[2]}/{parts[3]}{suffix}")
        elif len(parts) == 5 and parts[2] == "file":
            reg.root_at(int(parts[1]))
            self._redirect(f"/file/{parts[3]}/{parts[4]}{suffix}")
        else:
            self._error(HTTPStatus.NOT_FOUND, "no such page")

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
        try:
            if len(parts) == 2 and parts[0] == "hold":
                hold_id = parts[1]
                _pid, root = self.state.registry.owner_of("hold", hold_id)
            elif len(parts) == 4 and parts[0] == "p" and parts[2] == "hold":
                hold_id = parts[3]
                root = self.state.registry.root_at(int(parts[1]))
            else:
                self._error(HTTPStatus.NOT_FOUND, "no such page")
                return
            project = Project.load(root)
            h = get_hold(project, hold_id)
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
                self._render_hold(project, h, error=str(e), chosen=verdict, reason=reason or ""),
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
                project_href=self._project_href(project.root) or "/",
                list_href=self._list_href(),
                refresh=None,
                style=_STYLE,
            ),
        )

    # -- the event stream and the JSON routes (plan 3.5, 3.6) ---------------------------------

    def _stream_events(self) -> None:
        """Server-sent events until the client goes away: every event the watcher publishes,
        a comment line every few seconds in between so proxies and the browser keep the
        connection. The handler's thread is held for the life of the connection."""
        watcher = self.server.watcher
        q = watcher.subscribe()
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self._cookie_header()
            self.end_headers()
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while not watcher.stopped:
                try:
                    ev = q.get(timeout=10.0)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                self.wfile.write(ev.sse().encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            watcher.unsubscribe(q)

    def _api(self, parts: list[str]) -> Any:
        """The pages' data as JSON: `/api/fleet`, `/api/project/<id>`, `/api/hold/<id>`,
        `/api/run/<id>`. The same readers as the pages; nothing is computed only here."""
        reg = self.state.registry
        if parts == ["fleet"]:
            roots = self.state.roots
            refs = references(roots)
            projects: list[dict[str, Any]] = []
            cards: list[dict[str, Any]] = []
            for root in roots:
                entry = project_entry(root)
                item: dict[str, Any] = {
                    "project_id": reg.id_of(root),
                    "name": root.name,
                    "row": row(entry),
                    "sentence": sentence(entry),
                    "driver": _NO_DRIVER,
                }
                if "error" not in entry:
                    site = Site.load(root)
                    try:
                        cards += self._cards(root, site)
                        item["driver"] = self._driver(site, entry, refs)
                    finally:
                        site.store.close()
                else:
                    item["error"] = entry["error"]
                projects.append(item)
            return {
                "schema": "stringency.console_fleet/1",
                "projects": projects,
                "inbox": group_cards(cards),
            }
        if len(parts) == 2 and parts[0] == "project":
            root = reg.root_of(parts[1])
            site = Site.load(root)
            try:
                entry = project_entry(root)
                titles = {sid: site.pipeline.title(sid) for sid in site.pipeline.order()}
                return {
                    "schema": "stringency.console_project/1",
                    "project_id": parts[1],
                    "name": root.name,
                    "row": row(entry),
                    "sentence": sentence(entry),
                    "steps": (
                        [
                            {"step_id": sid, "title": titles[sid], "status": st}
                            for sid, st in site.step_statuses(entry["run"]["run_id"]).items()
                        ]
                        if entry.get("run")
                        else []
                    ),
                    "driver": self._driver(site, entry, references(self.state.roots)),
                    "holds": self._cards(root, site),
                    "timeline": timeline(site.store.conn, titles),
                }
            finally:
                site.store.close()
        if len(parts) == 2 and parts[0] == "hold":
            pid, root = reg.owner_of("hold", parts[1])
            project = Project.load(root)
            h = get_hold(project, parts[1])
            view = render(project, h)
            site = Site.load(root)
            try:
                hp = present_hold(site, h["hold_id"]) if h["kind"] != "confirm" else None
            finally:
                site.store.close()
            ctx = hold_context(h)
            return {
                "schema": "stringency.console_hold/1",
                "project_id": pid,
                "ask": ask_of(h, ctx),
                **view.to_json(),
                "sections": hp["sections"] if hp else [],
                "replicates": _replicates_for(project, h) if h["item_id"] is not None else [],
            }
        if len(parts) == 2 and parts[0] == "run":
            pid, root = reg.owner_of("run", parts[1])
            site = Site.load(root)
            try:
                return {
                    "schema": "stringency.console_run/1",
                    "project_id": pid,
                    **present_run(site, parts[1]),
                }
            finally:
                site.store.close()
        raise ConfigError("no such route")

    # -- rendering ----------------------------------------------------------------------------

    def _render_landing(self) -> str:
        cards: list[dict[str, Any]] = []
        board: list[dict[str, Any]] = []
        roots = self.state.roots
        refs = references(roots)
        for root in roots:
            entry = project_entry(root)
            drv: dict[str, Any] = _NO_DRIVER
            if "error" not in entry:
                site = Site.load(root)
                try:
                    cards += self._cards(root, site)
                    drv = self._driver(site, entry, refs)
                finally:
                    site.store.close()
            board.append(
                {
                    "name": root.name,
                    "href": self._project_href(root),
                    "cells": row(entry),
                    "sentence": sentence(entry),
                    "driver": drv,
                }
            )
        return LANDING_HTML.render(
            title="stringency projects",
            groups=group_cards(cards),
            n_holds=len(cards),
            board=board,
            columns=list(COLUMNS),
            n_projects=len(roots),
            user=self.state.user,
            host=self.state.host,
            read_only=self.state.read_only,
            refresh=REFRESH_SECONDS,
            style=_STYLE,
        )

    def _driver(
        self, site: Site, entry: dict[str, Any], refs: dict[tuple[str, str], float]
    ) -> dict[str, Any]:
        if not entry.get("run"):
            return _NO_DRIVER
        run = site.store.one("SELECT * FROM runs WHERE run_id = ?", (entry["run"]["run_id"],))
        if run is None:
            return _NO_DRIVER
        d = driver(site.store.conn, run, entry.get("step"), site.config.pipeline, refs)
        who = d["harness"] or "a terminal"
        if d["session"]:
            who += f", {d['session']}"
        d["who"] = f"{who}, {d['user']} on {d['host']}"
        return d

    def _render_project(self, root: Path) -> str:
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
                error=entry["error"],
                steps=[],
                holds=[],
                deliveries=[],
                confirm="",
                driver=None,
                timeline=[],
                **common,
            )
        site = Site.load(root)
        try:
            drv = self._driver(site, entry, references(self.state.roots))
            titles = {sid: site.pipeline.title(sid) for sid in site.pipeline.order()}
            runs = timeline(site.store.conn, titles)
            steps: list[dict[str, str]] = []
            if entry.get("run"):
                run_id = entry["run"]["run_id"]
                statuses = site.step_statuses(run_id)
                steps = [
                    {
                        "title": site.pipeline.title(s),
                        "status": (
                            skip_reason(site.store, run_id, s) or "skipped"
                            if statuses.get(s) == "skipped"
                            else statuses.get(s, "pending").replace("_", " ")
                        ),
                    }
                    for s in site.pipeline.order()
                ]
            holds = self._cards(root, site)
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
                deliveries.append({"when": d["ts"], "href": f"/run/{d['run_id']}", "files": files})
        finally:
            site.store.close()
        return PROJECT_HTML.render(
            error=None,
            steps=steps,
            holds=holds,
            deliveries=deliveries,
            confirm=entry.get("confirm", ""),
            driver=drv if drv is not _NO_DRIVER else None,
            timeline=runs,
            **common,
        )

    def _render_run(self, root: Path, run_id: str) -> str:
        site = Site.load(root)
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
                        "href": f"/file/{run_id}/{name}",
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
            project_href=self._project_href(root) or "/",
            refresh=None,
            style=_STYLE,
        )

    def _send_file(self, root: Path, run_id: str, name: str) -> None:
        """One delivered file, only when `index.json` lists its name; never a path."""
        if "/" in name or "\\" in name or name in ("", ".", "..") or name.startswith("."):
            raise ConfigError("no such file")
        site = Site.load(root)
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
            list_href=self._list_href(),
            project_href=self._project_href(project.root) or "/",
            post_href=f"/hold/{h['hold_id']}",
            refresh=None,
            style=_STYLE,
        )


class ReviewHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, address: tuple[str, int], state: ServerState, *, poll_seconds: float | None = None
    ) -> None:
        super().__init__(address, ReviewHandler)
        self.state = state
        kw = {"poll_seconds": poll_seconds} if poll_seconds is not None else {}
        self.watcher = Watcher(state.registry, **kw)
        self.watcher.start()

    def server_close(self) -> None:
        self.watcher.stop()
        super().server_close()


def make_server(
    roots: list[Path],
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    token: str | None = None,
    read_only: bool = False,
    projects_dirs: list[Path] | None = None,
    poll_seconds: float | None = None,
) -> ReviewHTTPServer:
    """Build the server without serving (tests bind port 0). Identity is the OS user running it.
    `roots` are served wherever they are; `projects_dirs` are rescanned while the server runs."""
    import socket

    from stringency.review import current_user

    registry = Registry(explicit=list(roots), dirs=list(projects_dirs or []))
    registry.refresh(force=True)
    state = ServerState(
        registry=registry,
        token=token or secrets.token_urlsafe(24),
        user=current_user(),
        host=socket.gethostname(),
        read_only=read_only,
    )
    return ReviewHTTPServer((bind, port), state, poll_seconds=poll_seconds)


def serve(
    projects: list[Path],
    projects_dir: list[Path] | Path | None,
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    read_only: bool = False,
    token_file: Path | None = None,
) -> None:
    """Print the URL with its token once, then serve until interrupted."""
    dirs = [projects_dir] if isinstance(projects_dir, Path) else list(projects_dir or [])
    token = read_token_file(token_file) if token_file is not None else None
    srv = make_server(
        projects, bind=bind, port=port, token=token, read_only=read_only, projects_dirs=dirs
    )
    host, actual = str(srv.server_address[0]), int(srv.server_address[1])
    mode = "read-only, no verdicts" if read_only else "verdicts recorded here carry via: web"
    print(
        f"stringency review --serve: {len(srv.state.roots)} project(s) as {srv.state.user}; "
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
