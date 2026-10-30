"""Run-time CPU and memory allocation of a step (PLAN L130, the owner's decision of 2026-10-29).

A module's `resources` (`cpus`, `memory`, `timeout`) in `module.yml` are its request. The
operator may give another request for one invocation (`--cpus`, `--memory` on `run`, `call`,
`exec` and `controls run`), and the policy may cap both (`resources: {max_cpus,
max_memory_gb}`; absent means no cap). Per value, the allocation is the invocation's override
when given, else the module's, and never more than the policy's cap; each value records the
source it came from (`module`, `override` or `policy`). The allocation reaches the script in
`job.json` (`resources: {cpus, memory_gb, timeout_s}`) and in the environment
(`STRINGENCY_CPUS`, `STRINGENCY_MEMORY_GB` and the usual thread variables).

Nothing here reads or writes the trace; `steps` writes the allocation into the step's event.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency.exit_codes import ConfigError

THREAD_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
SOURCES = ("module", "override", "policy")

_MEMORY = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([kmgt]?)(?:i?b)?\s*$", re.IGNORECASE)
_MEMORY_GB = {"k": 1 / (1024 * 1024), "m": 1 / 1024, "g": 1.0, "t": 1024.0, "": 1.0}
_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-z]*)\s*$", re.IGNORECASE)
_DURATION_S = {
    "": 1,
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
}


def _number(x: float) -> int | float:
    """An integral value as an int (`64`, not `64.0`), so job.json reads as written."""
    return int(x) if float(x).is_integer() else round(x, 3)


def parse_memory_gb(value: str | float | None) -> int | float | None:
    """`8GB`, `64G`, `512MB`, `1TB` or a bare number (gigabytes) as gigabytes; None for None.
    Raises ConfigError on anything else."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        n = float(value)
    else:
        m = _MEMORY.match(str(value))
        if m is None:
            raise ConfigError(f"memory {value!r}: expected a size such as 64GB or 512MB")
        n = float(m.group(1)) * _MEMORY_GB[m.group(2).lower()]
    if n <= 0:
        raise ConfigError(f"memory {value!r} must be more than zero")
    return _number(n)


def parse_duration_s(value: str | float | None) -> int | None:
    """`30min`, `30m`, `12h`, `90s`, `2d` or a bare number (seconds) as whole seconds; None for
    None. Raises ConfigError on anything else."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    m = _DURATION.match(str(value))
    unit = m.group(2).lower() if m else None
    if m is None or unit not in _DURATION_S:
        raise ConfigError(f"timeout {value!r}: expected a duration such as 30min, 2h or 90s")
    return int(float(m.group(1)) * _DURATION_S[unit])


@dataclass(frozen=True)
class Override:
    """The invocation's request (`--cpus`, `--memory`); None where the operator gave none."""

    cpus: int | None = None
    memory_gb: int | float | None = None

    @classmethod
    def from_options(cls, cpus: int | None, memory: str | None) -> Override | None:
        """The override from the CLI options, or None when neither is given."""
        if cpus is None and memory is None:
            return None
        if cpus is not None and cpus <= 0:
            raise ConfigError("--cpus must be a whole number above zero")
        try:
            mem = parse_memory_gb(memory)
        except ConfigError as e:
            raise ConfigError(f"--memory: {e}") from None
        return cls(cpus=cpus, memory_gb=mem)


@dataclass(frozen=True)
class Allocation:
    """What a step runs with. `source` names, per key, where each value came from."""

    cpus: int | None = None
    memory_gb: int | float | None = None
    timeout_s: int | None = None
    source: dict[str, str] = field(default_factory=dict)

    def job_value(self) -> dict[str, Any]:
        """The `resources` mapping of `job.json` and of the executor's Job."""
        return {"cpus": self.cpus, "memory_gb": self.memory_gb, "timeout_s": self.timeout_s}

    def event_payload(self) -> dict[str, Any]:
        """What the step's started event carries: the allocation and each value's source."""
        return {"resources": self.job_value(), "resources_source": dict(self.source)}


def _pick(
    module_value: int | float | None,
    override_value: int | float | None,
    cap: int | float | None,
) -> tuple[int | float | None, str]:
    """min(the override if given else the module's value, the cap): the value and its source."""
    value: int | float | None = module_value
    source = "module"
    if override_value is not None:
        value, source = override_value, "override"
    if cap is not None and (value is None or value > cap):
        return cap, "policy"
    return value, source


def allocate(
    module_resources: Any,
    *,
    override: Override | None = None,
    max_cpus: int | None = None,
    max_memory_gb: float | None = None,
    timeout_s: float | None = None,
) -> Allocation:
    """The allocation of one step. `module_resources` is the manifest's `resources` block
    (`cpus`, `memory`, `timeout`); `timeout_s`, when given, replaces the module's timeout (an
    `exec` step runs under the policy's `open.exec_timeout_s`) and is recorded as `policy`."""
    ov = override or Override()
    mcpus = getattr(module_resources, "cpus", None)
    # a module value that does not parse requests nothing (lint warns on it): a run that ran
    # before the allocation existed is not refused for it now
    try:
        mmem = parse_memory_gb(getattr(module_resources, "memory", None))
    except ConfigError:
        mmem = None
    cpus, cpus_src = _pick(mcpus, ov.cpus, max_cpus)
    mem, mem_src = _pick(mmem, ov.memory_gb, max_memory_gb)
    timeout: int | None = None
    if timeout_s is not None:
        timeout, t_src = int(timeout_s), "policy"
    else:
        try:
            timeout = parse_duration_s(getattr(module_resources, "timeout", None))
        except ConfigError:
            timeout = None
        t_src = "module"
    return Allocation(
        cpus=None if cpus is None else int(cpus),
        memory_gb=None if mem is None else _number(float(mem)),
        timeout_s=timeout,
        source={"cpus": cpus_src, "memory_gb": mem_src, "timeout_s": t_src},
    )


def env_for(resources: Mapping[str, Any]) -> dict[str, str]:
    """The environment a job's allocation sets: `STRINGENCY_CPUS` and the thread variables to
    the CPUs, `STRINGENCY_MEMORY_GB` to the memory; a value that is unset sets nothing."""
    env: dict[str, str] = {}
    cpus = resources.get("cpus")
    if cpus is not None:
        env["STRINGENCY_CPUS"] = str(int(cpus))
        for v in THREAD_VARS:
            env[v] = str(int(cpus))
    mem = resources.get("memory_gb")
    if mem is not None:
        env["STRINGENCY_MEMORY_GB"] = str(_number(float(mem)))
    return env


# -- lint: a script that takes the machine's core count -------------------------------------

# what the text check matches: a call that asks the host for its core count
CORE_COUNT = re.compile(
    r"parallel::detectCores|\bdetectCores\s*\(|\bos\.cpu_count\s*\(|"
    r"\bmultiprocessing\.cpu_count\s*\("
)
# what counts as reading the job's allocation: the job's `resources` key as a quoted name
# (`job["resources"]`, `job.get('resources')`, `job[["resources"]]`), `$resources` (R), or the
# variable; prose that says "resources" in a trailing comment does not count
READS_ALLOCATION = re.compile(r"""["']resources["']|\$resources\b|STRINGENCY_CPUS""")


def host_core_reads(script: Path) -> list[tuple[int, str]]:
    """Reads, read-only: one script. Each (line number, text) that asks the host for its core
    count (`detectCores(`, `parallel::detectCores`, `os.cpu_count(`, `multiprocessing.cpu_count(`)
    when no line of the same file reads the job's allocation (`READS_ALLOCATION`); [] when the
    file reads the allocation or asks nothing. Comment lines are skipped for both."""
    from stringency.egress import _is_comment

    try:
        text = script.read_text(errors="replace")
    except OSError:
        return []
    suffix = script.suffix.lower()
    hits: list[tuple[int, str]] = []
    reads = False
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or _is_comment(line, suffix):
            continue
        if CORE_COUNT.search(line):
            hits.append((n, line.strip()))
        if READS_ALLOCATION.search(line):
            reads = True
    return [] if reads else hits
