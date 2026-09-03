"""Lint (design 13). Errors fail; warnings do not. Filled in at M3."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LintReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [f"error: {e}" for e in self.errors] + [f"warning: {w}" for w in self.warnings]
        if not lines:
            lines = ["lint: no errors, no warnings"]
        return "\n".join(lines)


def lint_path(path: Path) -> LintReport:
    """Lint a module directory or a method repo. M2 stub: loads manifests only."""
    from stringency.exit_codes import ConfigError
    from stringency.modules import ModuleIndex, load_module

    report = LintReport()
    try:
        if (path / "module.yml").exists():
            load_module(path)
        else:
            ModuleIndex(path)
    except ConfigError as e:
        report.errors.append(str(e))
    return report
