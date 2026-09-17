"""`hash_path`: a declared input may be a file or a directory (a Xenium region bundle, a
directory of punch coordinates). Directory hashes cover relative paths and contents."""

from __future__ import annotations

from pathlib import Path

from stringency import hashing


def _bundle(root: Path, cells: str = "a,b\n1,2\n") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "cells.parquet").write_text(cells)
    (root / "analysis").mkdir(exist_ok=True)
    (root / "analysis" / "x.csv").write_text("x\n")
    return root


def test_hash_path_file_equals_hash_file(tmp_path: Path) -> None:
    f = tmp_path / "t.csv"
    f.write_text("a\n")
    assert hashing.hash_path(f) == hashing.hash_file(f)


def test_hash_path_dir_equals_hash_dir_and_is_content_based(tmp_path: Path) -> None:
    a = _bundle(tmp_path / "a")
    b = _bundle(tmp_path / "b")
    assert hashing.hash_path(a) == hashing.hash_dir(a) == hashing.hash_path(b)
    changed = _bundle(tmp_path / "c", cells="a,b\n1,3\n")
    assert hashing.hash_path(changed) != hashing.hash_path(a)
    renamed = _bundle(tmp_path / "d")
    (renamed / "analysis" / "x.csv").rename(renamed / "analysis" / "y.csv")
    assert hashing.hash_path(renamed) != hashing.hash_path(a)


def test_path_size_sums_directory(tmp_path: Path) -> None:
    b = _bundle(tmp_path / "s")
    assert hashing.path_size(b) == sum(p.stat().st_size for p in b.rglob("*") if p.is_file())
    f = tmp_path / "one.txt"
    f.write_text("abc")
    assert hashing.path_size(f) == 3


def test_sidecar_for_directory_output(tmp_path: Path) -> None:
    """A step output may be a directory (a set of punch bundles): its sidecar sits beside it,
    carries the tree hash, and sums the size over the files (record_output uses the same
    helpers)."""
    import json

    from stringency.artifacts import sidecar_path, write_sidecar

    out = _bundle(tmp_path / "step" / "punch_bundles.dir")
    digest = hashing.hash_path(out)
    sc = write_sidecar(
        out, run_id="R", step_id="01_split", action_id=None, digest=digest, kind="object", name="x"
    )
    assert sc == sidecar_path(out) and sc.parent == out.parent
    data = json.loads(sc.read_text())
    assert data["size"] == hashing.path_size(out)
    assert digest == hashing.hash_dir(out)
