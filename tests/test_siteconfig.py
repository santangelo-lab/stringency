"""The site configuration: the user's file over the one beside the install."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from stringency import siteconfig


def test_install_config_is_read_under_the_users_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "lib"
    venv = prefix / "versions" / "0.2.38"
    venv.mkdir(parents=True)
    monkeypatch.setattr(sys, "prefix", str(venv))
    assert siteconfig.install_config_path() == prefix / "config.yml"
    assert siteconfig.executor() is None
    (prefix / "config.yml").write_text("executor: local\nimages_root: /imgs\n")
    assert siteconfig.executor() == "local"
    assert siteconfig.images_root() == Path("/imgs")
    user = siteconfig.config_path()
    user.parent.mkdir(parents=True)
    user.write_text("executor: apptainer\n")
    assert siteconfig.executor() == "apptainer"  # the user's key wins
    assert siteconfig.images_root() == Path("/imgs")  # the install's other key stays


def test_no_install_config_from_a_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "checkout" / ".venv"))
    assert siteconfig.install_config_path() is None
    assert siteconfig.load() == {}
