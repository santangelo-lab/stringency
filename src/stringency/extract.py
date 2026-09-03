"""Run a plugin's state extractor on an object output through the executor (design 4.2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from stringency.executor.base import Executor, Job
from stringency.executor.local import interpreter_for
from stringency.exit_codes import FailedError
from stringency.plugins import Plugin
from stringency.state import Extraction


def extract_object(
    plugin: Plugin,
    executor: Executor,
    *,
    object_type: str,
    object_path: Path,
    design: dict[str, Any],
    env_name: str,
    workdir: Path,
) -> Extraction:
    """Run the extractor tool for `object_type` and parse its JSON envelope."""
    ot = plugin.object_types.get(object_type)
    if ot is None:
        raise FailedError(f"plugin {plugin.name} has no object type {object_type}")
    tool = plugin.tools.get(ot.extractor)
    if tool is None:
        raise FailedError(f"plugin {plugin.name} declares no tool {ot.extractor}")
    workdir.mkdir(parents=True, exist_ok=True)
    design_path = workdir / "design.json"
    design_path.write_text(json.dumps(design, sort_keys=True))
    job = Job(
        command=[*interpreter_for(tool.script), str(object_path), str(design_path)],
        env_name=tool.env or env_name,
        cwd=workdir,
        stdout_path=workdir / "extract.stdout",
        stderr_path=workdir / "extract.stderr",
    )
    res = executor.run(job)
    if res.exit_code != 0:
        raise FailedError(
            f"extractor {ot.extractor} exited {res.exit_code} on {object_path}: "
            f"{res.stderr().strip()[-500:]}"
        )
    try:
        summary = json.loads(res.stdout())
    except json.JSONDecodeError as e:
        raise FailedError(f"extractor {ot.extractor} printed invalid JSON: {e}") from None
    if not isinstance(summary, dict):
        raise FailedError(f"extractor {ot.extractor} did not print a JSON object")
    ext_id = str(summary.get("extractor", ot.extractor_id))
    name, _, version = ext_id.partition("@")
    return Extraction(extractor=name, version=version or "0", summary=summary)
