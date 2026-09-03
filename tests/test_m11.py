"""M11: api adapter against a recorded response, apptainer executor, method-repo template, specs."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from stringency.executor.apptainer import ApptainerExecutor
from stringency.executor.base import Job
from stringency.harness.api import ApiHarness
from stringency.harness.base import Request, Sampling
from stringency.lint import lint_path

ROOT = Path(__file__).parent.parent
RECORDED = Path(__file__).parent / "fixtures" / "harness" / "api_recorded_response.json"


class FakeMessages:
    def __init__(self, recorded: dict) -> None:
        self.recorded = recorded
        self.calls: list[dict] = []

    def create(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        r = self.recorded
        return SimpleNamespace(
            model=r["model"],
            stop_reason=r["stop_reason"],
            stop_details=None,
            content=[SimpleNamespace(type="text", text=r["text"])],
            usage=SimpleNamespace(
                input_tokens=r["usage"]["input_tokens"], output_tokens=r["usage"]["output_tokens"]
            ),
        )


def test_api_adapter_replays_recorded_response() -> None:
    recorded = json.loads(RECORDED.read_text())
    fake = SimpleNamespace(messages=FakeMessages(recorded))
    h = ApiHarness(client=fake)
    req = Request(1, "n-1", "prompt", {"type": "object"}, ("A",), "m@1", "prompt.md")
    inv = h.invoke(
        "prompt", {"type": "object", "required": ["items"]}, sampling=Sampling(), request=req
    )
    assert inv.model_requested == "claude-opus-5" and inv.model_resolved == recorded["model"]
    assert inv.structured == json.loads(recorded["text"])
    assert (
        inv.tokens_in == 412
        and inv.tokens_out == 233
        and inv.via == "direct"
        and inv.isolation == "enforced"
    )
    call = fake.messages.calls[0]
    assert call["output_config"] == {
        "format": {"type": "json_schema", "schema": {"type": "object", "required": ["items"]}}
    }
    assert call["model"] == "claude-opus-5" and "thinking" not in call


def test_api_adapter_records_refusal_and_unknowns() -> None:
    recorded = {
        "model": None,
        "stop_reason": "refusal",
        "text": "",
        "usage": {"input_tokens": None, "output_tokens": None},
    }
    h = ApiHarness(model="claude-opus-5", client=SimpleNamespace(messages=FakeMessages(recorded)))
    req = Request(1, "n", "p", {}, ("A",), "m@1", "t")
    inv = h.invoke("p", {}, sampling=Sampling(), request=req)
    assert (
        inv.structured is None
        and inv.model_resolved == "unknown"
        and inv.error is not None
        and "refusal" in inv.error
    )


def _manifest(envs: Path, image: Path, sha: str) -> None:
    envs.mkdir(parents=True, exist_ok=True)
    (envs / "manifest.yml").write_text(
        f"environments:\n  e1:\n    image: {image}\n    sha256: {sha}\n"
    )


def test_apptainer_digest_verified_against_manifest(tmp_path: Path) -> None:
    envs = tmp_path / "envs"
    image = tmp_path / "env.sif"
    image.write_bytes(b"not really a sif")
    sha = hashlib.sha256(image.read_bytes()).hexdigest()
    _manifest(envs, image, sha)
    ex = ApptainerExecutor(envs)
    assert ex.env_digest("e1") == sha
    assert ex.env_digest("missing") is None
    _manifest(envs, image, "0" * 64)
    assert ApptainerExecutor(envs).env_digest("e1") is None  # digest disagrees with the file


@pytest.mark.apptainer
@pytest.mark.skipif(
    shutil.which("apptainer") is None,
    reason="apptainer not on PATH: apptainer executor test SKIPPED",
)
def test_apptainer_runs_minimal_sif(tmp_path: Path) -> None:  # pragma: no cover
    import subprocess

    sif = tmp_path / "alpine.sif"
    subprocess.run(
        ["apptainer", "pull", str(sif), "docker://alpine:3.19"], check=True, capture_output=True
    )
    envs = tmp_path / "envs"
    _manifest(envs, sif, hashlib.sha256(sif.read_bytes()).hexdigest())
    ex = ApptainerExecutor(envs)
    res = ex.run(Job(command=["/bin/echo", "hello"], env_name="e1", cwd=tmp_path / "w"))
    assert res.exit_code == 0 and "hello" in res.stdout() and res.env_digest is not None


def test_apptainer_without_image_fails_cleanly(tmp_path: Path) -> None:
    envs = tmp_path / "envs"
    envs.mkdir()
    (envs / "manifest.yml").write_text("environments: {}\n")
    res = ApptainerExecutor(envs, binary="definitely-not-apptainer").run(
        Job(command=["true"], env_name="e1", cwd=tmp_path / "w")
    )
    assert res.exit_code == 127 and "no image" in res.stderr()


def test_method_repo_template_passes_lint() -> None:
    report = lint_path(ROOT / "templates" / "method-repo")
    assert report.ok, report.render()


def test_spec_documents_present() -> None:
    for name in (
        "module-contract.md",
        "predicate-contract.md",
        "trace-schema.md",
        "DECISIONS.md",
        "DEVIATIONS.md",
    ):
        text = (ROOT / "spec" / name).read_text()
        assert text.startswith("# "), name


def test_singlecell_plugin_listed_when_installed() -> None:
    pytest.importorskip("stringency_singlecell")
    from typer.testing import CliRunner

    from stringency.cli.app import app

    r = CliRunner().invoke(app, ["plugins", "list"])
    assert "stringency-singlecell" in r.output and "stringency-toy" in r.output
