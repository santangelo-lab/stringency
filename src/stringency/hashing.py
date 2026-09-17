"""blake3 over files, directories, and canonical JSON.

Functions return bare lowercase hex. Fields the design shows with an algorithm prefix
(state `digest`, action `inputs`) use `prefixed()`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import blake3

CHUNK = 1 << 20


def hash_bytes(data: bytes) -> str:
    return blake3.blake3(data).hexdigest()


def hash_text(text: str) -> str:
    return hash_bytes(text.encode("utf-8"))


def hash_file(path: Path | str) -> str:
    h = blake3.blake3()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def hash_dir(path: Path | str) -> str:
    """Hash a directory as the sorted sequence of (relative path, content hash)."""
    root = Path(path)
    h = blake3.blake3()
    for p in sorted(q for q in root.rglob("*") if q.is_file()):
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(bytes.fromhex(hash_file(p)))
        h.update(b"\0")
    return h.hexdigest()


def hash_path(path: Path | str) -> str:
    """Content hash of an input: `hash_file` for a file, `hash_dir` for a directory (a Xenium
    region bundle or a directory of punch coordinates is one declared input)."""
    p = Path(path)
    return hash_dir(p) if p.is_dir() else hash_file(p)


def path_size(path: Path | str) -> int:
    """Bytes in a file, or summed over every file under a directory."""
    p = Path(path)
    if p.is_dir():
        return sum(q.stat().st_size for q in p.rglob("*") if q.is_file())
    return p.stat().st_size


def canonical_json(obj: Any) -> str:
    """Sorted keys, no whitespace, no NaN. Stable under key reordering."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def hash_json(obj: Any) -> str:
    return hash_text(canonical_json(obj))


def prefixed(hex_digest: str, algo: str = "blake3") -> str:
    return f"{algo}:{hex_digest}"


def strip_prefix(digest: str) -> str:
    return digest.split(":", 1)[1] if ":" in digest else digest
