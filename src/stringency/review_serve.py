"""`stringency review --serve`: a localhost form for verdicts (design 7.5 `via: web`, 14.1;
`spec/plans/ux-two-audiences.md` section 5.2).

The reviewer starts it under their own account, usually through an SSH tunnel
(`scripts/review-page.sh`). It lists the open holds of one or more projects, shows a hold exactly
as `review_render.render` prints it, and records the verdict through `record_review` with
`via_override="web"`, so every rule the terminal path applies (identity, profile, required
reason, replicate, correction) applies here too. A random token printed once at start is
required on every request; the server binds to loopback unless told otherwise.

Reads: what `review_render.render` and `review.queue` read. Writes: nothing itself; a POST
writes through `record_review` (reviews, holds, consensus, steps, step_events, artifacts).
"""

from __future__ import annotations

import secrets
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from jinja2 import Environment, StrictUndefined

from stringency.board import refresh_if_present
from stringency.exit_codes import ConfigError, RefusedError
from stringency.project import Project
from stringency.review import _replicates_for, get_hold, queue, record_review
from stringency.review_render import render

DEFAULT_PORT = 8765
DEFAULT_BIND = "127.0.0.1"


def discover(projects: list[Path], projects_dir: Path | None) -> list[Path]:
    """Project roots: the ones named, plus every child of `projects_dir` to depth two that holds
    a `stringency.yml`. Ordered as given, then by path."""
    roots: list[Path] = [p.resolve() for p in projects]
    if projects_dir is not None:
        base = projects_dir.resolve()
        found: list[Path] = []
        for child in sorted(base.iterdir()) if base.is_dir() else []:
            if not child.is_dir():
                continue
            if (child / "stringency.yml").exists():
                found.append(child)
                continue
            for grand in sorted(child.iterdir()):
                if grand.is_dir() and (grand / "stringency.yml").exists():
                    found.append(grand)
        roots += [f for f in found if f not in roots]
    for r in roots:
        if not (r / "stringency.yml").exists():
            raise ConfigError(f"{r} is not a stringency project (no stringency.yml)")
    if not roots:
        raise ConfigError("review --serve needs --project <path> or --projects <dir>")
    return roots


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
fieldset { border: 1px solid #ddd; margin: 1em 0; padding: 0.6em 1em; }
label { display: block; margin: 0.3em 0; }
textarea, select { font: inherit; width: 100%; max-width: 40em; }
button { font: inherit; padding: 0.4em 1.2em; }
"""

LIST_HTML = _ENV.from_string(
    """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>stringency review</title><style>{{ style }}</style></head>
<body>
<h1>Open holds</h1>
<p class="note">Served by stringency review --serve for {{ user }} on {{ host }}. A verdict recorded here is
recorded as this account's, via web. The list is read fresh on every load.</p>
{% if rows %}
<table>
<tr><th>project</th><th>step</th><th>kind</th><th>item</th><th>waits on</th><th>open for</th></tr>
{% for r in rows %}
<tr>
<td><a href="{{ r.href }}">{{ r.project }}</a></td>
<td>{{ r.step }}</td><td>{{ r.kind }}</td><td>{{ r.item }}</td><td>{{ r.waits_on }}</td><td>{{ r.age }}</td>
</tr>
{% endfor %}
</table>
{% else %}
<p>No unresolved holds in {{ n_projects }} project(s).</p>
{% endif %}
</body>
</html>
"""
)

HOLD_HTML = _ENV.from_string(
    """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>stringency hold {{ hold_id }}</title><style>{{ style }}</style></head>
<body>
<p><a href="{{ list_href }}">All open holds</a></p>
<h1>Hold {{ hold_id }} ({{ kind }}){% if step_id %} on step {{ step_id }}{% endif %}{% if item_id %}, item {{ item_id }}{% endif %}</h1>
<p class="note">Project {{ project }}. What follows is what stringency review prints at a terminal; the form
records the same verdicts by the same rules.</p>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<pre>{{ text }}</pre>
{% if resolved %}
<p>This hold was resolved by review {{ resolved }}.</p>
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
</body>
</html>
"""
)

DONE_HTML = _ENV.from_string(
    """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>stringency review recorded</title><style>{{ style }}</style></head>
<body>
<h1>Recorded</h1>
<p>Review {{ review_id }}: {{ verdict }} on hold {{ hold_id }} via {{ via }}{% if step_status %}; step {{ step_status }}, run {{ run_status }}{% endif %}.</p>
<p><a href="{{ list_href }}">Back to the open holds</a></p>
</body>
</html>
"""
)

ERROR_HTML = _ENV.from_string(
    """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>stringency review: {{ status }}</title><style>{{ style }}</style></head>
<body>
<h1>{{ status }}</h1>
<p class="error">{{ message }}</p>
</body>
</html>
"""
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


@dataclass
class ServerState:
    roots: list[Path]
    token: str
    user: str
    host: str


class ReviewHandler(BaseHTTPRequestHandler):
    """One request at a time per thread; each request opens its own `Project` (and store)."""

    server: ReviewHTTPServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        sys.stderr.write("review --serve: " + (format % args) + "\n")

    # -- helpers ------------------------------------------------------------------------------

    @property
    def state(self) -> ServerState:
        return self.server.state

    def _send(self, status: HTTPStatus, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._send(
            status,
            ERROR_HTML.render(
                status=f"{status.value} {status.phrase}", message=message, style=_STYLE
            ),
        )

    def _token_ok(self, params: dict[str, list[str]]) -> bool:
        given = params.get("t", [""])[0]
        return bool(given) and secrets.compare_digest(given, self.state.token)

    def _list_href(self) -> str:
        return f"/?t={self.state.token}"

    def _project(self, index: int) -> Project:
        if index < 0 or index >= len(self.state.roots):
            raise ConfigError(f"no project {index}")
        return Project.load(self.state.roots[index])

    # -- routes -------------------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        params = parse_qs(url.query)
        if not self._token_ok(params):
            self._error(
                HTTPStatus.FORBIDDEN, "this page needs the token printed when the server started"
            )
            return
        if url.path == "/":
            self._send(HTTPStatus.OK, self._render_list())
            return
        parts = [p for p in url.path.split("/") if p]
        if len(parts) == 4 and parts[0] == "p" and parts[2] == "hold":
            try:
                project = self._project(int(parts[1]))
                h = get_hold(project, parts[3])
            except (ConfigError, ValueError) as e:
                self._error(HTTPStatus.NOT_FOUND, str(e))
                return
            self._send(HTTPStatus.OK, self._render_hold(int(parts[1]), project, h))
            return
        self._error(HTTPStatus.NOT_FOUND, "no such page")

    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        if not self._token_ok(form) and not self._token_ok(parse_qs(url.query)):
            self._error(
                HTTPStatus.FORBIDDEN, "this page needs the token printed when the server started"
            )
            return
        parts = [p for p in url.path.split("/") if p]
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
                review_id=result.review_id,
                verdict=result.verdict,
                hold_id=result.hold_id,
                via=result.via,
                step_status=result.step_status,
                run_status=result.run_status,
                list_href=self._list_href(),
                style=_STYLE,
            ),
        )

    # -- rendering ----------------------------------------------------------------------------

    def _render_list(self) -> str:
        rows: list[dict[str, str]] = []
        for i, root in enumerate(self.state.roots):
            project = Project.load(root)
            for h in queue(project):
                step = h["step_id"]
                title = (
                    project.pipeline.title(step)
                    if step and project.pipeline.has_step(step)
                    else (step or "project")
                )
                rows.append(
                    {
                        "project": root.name,
                        "step": title,
                        "kind": h["kind"],
                        "item": h["item_id"] or "",
                        "waits_on": h["waits_on_role"],
                        "age": _age(h["created"]),
                        "href": f"/p/{i}/hold/{h['hold_id']}?t={self.state.token}",
                    }
                )
        return LIST_HTML.render(
            rows=rows,
            n_projects=len(self.state.roots),
            user=self.state.user,
            host=self.state.host,
            style=_STYLE,
        )

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
        return HOLD_HTML.render(
            hold_id=h["hold_id"],
            kind=h["kind"],
            step_id=h["step_id"],
            item_id=h["item_id"],
            project=project.root.name,
            text=view.text,
            verdicts=view.verdicts,
            replicates=replicates,
            vocabulary=vocabulary,
            chosen=chosen,
            reason=reason,
            error=error,
            resolved=h["resolved_by_review"],
            token=self.state.token,
            list_href=self._list_href(),
            post_href=f"/p/{index}/hold/{h['hold_id']}",
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
) -> ReviewHTTPServer:
    """Build the server without serving (tests bind port 0). Identity is the OS user running it."""
    import socket

    from stringency.review import current_user

    state = ServerState(
        roots=list(roots),
        token=token or secrets.token_urlsafe(24),
        user=current_user(),
        host=socket.gethostname(),
    )
    return ReviewHTTPServer((bind, port), state)


def serve(
    projects: list[Path],
    projects_dir: Path | None,
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
) -> None:
    """Print the URL with its token once, then serve until interrupted."""
    roots = discover(projects, projects_dir)
    srv = make_server(roots, bind=bind, port=port)
    host, actual = str(srv.server_address[0]), int(srv.server_address[1])
    print(
        f"stringency review --serve: {len(roots)} project(s) as {srv.state.user}; "
        f"open http://{host}:{actual}/?t={srv.state.token}",
        flush=True,
    )
    print("verdicts recorded here carry via: web; stop with Ctrl-C", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
