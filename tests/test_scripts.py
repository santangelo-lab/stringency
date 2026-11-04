"""The install scripts' shell logic that a Mac setup tripped on (2026-11-04): the interpreter
choice refuses a virtual environment's python, and the bootstrap's closing text survives a
missing config file under `set -euo pipefail`."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_install_sh_never_picks_a_venv_python(tmp_path: Path) -> None:
    src = (ROOT / "scripts" / "install.sh").read_text()
    m = re.search(r"^pick_python\(\) \{.*?^\}$", src, re.S | re.M)
    assert m is not None
    fn = m.group(0)
    # a PATH whose first python3 is this test's own interpreter when it is a venv's, else a
    # shim that reports itself as one
    bin_dir = tmp_path / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    shim = bin_dir / "python3"
    shim.write_text(
        "#!/bin/sh\n"
        f"exec {sys.executable} -c \"import sys; sys.prefix = sys.base_prefix + '/venv'; "
        'exec(sys.argv[1])" "$2"\n'
    )
    shim.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    r = subprocess.run(
        ["bash", "-c", fn + "\npick_python"], capture_output=True, text=True, env=env, check=False
    )
    assert str(shim) not in r.stdout
    if r.returncode == 0:
        chosen = r.stdout.strip()
        assert chosen and "/venv/" not in chosen


def test_bootstrap_closing_text_survives_missing_config(tmp_path: Path) -> None:
    src = (ROOT / "scripts" / "bootstrap.sh").read_text()
    line = next(x for x in src.splitlines() if x.startswith("executor=$("))
    r = subprocess.run(
        ["bash", "-c", f'set -euo pipefail; prefix={tmp_path}; {line}\necho "[$executor]"'],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path)},
        check=False,
    )
    assert r.returncode == 0 and r.stdout.strip() == "[]"
    (tmp_path / "config.yml").write_text("executor: local\n")
    r = subprocess.run(
        ["bash", "-c", f'set -euo pipefail; prefix={tmp_path}; {line}\necho "[$executor]"'],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path / "nohome")},
        check=False,
    )
    assert r.returncode == 0 and r.stdout.strip() == "[local]"
