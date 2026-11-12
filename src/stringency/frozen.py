"""Read-only JSON containers for an admitted Action's values (L106).

`FrozenDict` and `FrozenList` are `dict` and `list` to every reader (`isinstance`, `json`,
`jsonschema`, equality with a plain value), and refuse every method that would change them in
place. A copy (`dict(x)`, `list(x)`, `x.copy()`, `copy.deepcopy(x)`) is an ordinary mutable
value, so a caller that wants to change something changes its own copy and never the Action.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NoReturn

READ_ONLY = "an Action's values are read-only once built (L106); change a copy"


def _refuse(self: Any, *args: Any, **kwargs: Any) -> NoReturn:
    raise TypeError(READ_ONLY)


class FrozenDict(dict[str, Any]):
    """A `dict` whose contents cannot be changed in place."""

    __slots__ = ()

    __setitem__ = _refuse
    __delitem__ = _refuse
    __ior__ = _refuse
    clear = _refuse
    pop = _refuse
    popitem = _refuse
    setdefault = _refuse
    update = _refuse

    def __reduce__(self) -> tuple[Any, ...]:
        return (FrozenDict, (dict(self),))

    def __copy__(self) -> dict[str, Any]:
        return dict(self)

    def __deepcopy__(self, memo: dict[int, Any]) -> Any:
        return thaw(self)


class FrozenList(list[Any]):
    """A `list` whose contents cannot be changed in place."""

    __slots__ = ()

    __setitem__ = _refuse
    __delitem__ = _refuse
    __iadd__ = _refuse
    __imul__ = _refuse
    append = _refuse
    extend = _refuse
    insert = _refuse
    pop = _refuse
    remove = _refuse
    clear = _refuse
    sort = _refuse
    reverse = _refuse

    def __reduce__(self) -> tuple[Any, ...]:
        return (FrozenList, (list(self),))

    def __copy__(self) -> list[Any]:
        return list(self)

    def __deepcopy__(self, memo: dict[int, Any]) -> Any:
        return thaw(self)


def freeze(value: Any) -> Any:
    """A deep read-only copy of a JSON-like value: mappings become `FrozenDict`, lists and
    tuples `FrozenList`, everything else is kept (strings, numbers, booleans and None are
    immutable already). The caller's value is never shared with the result."""
    if isinstance(value, FrozenDict | FrozenList):
        return value  # built by freeze, so its members are frozen too
    if isinstance(value, Mapping):
        return FrozenDict({str(k): freeze(v) for k, v in value.items()})
    if isinstance(value, list | tuple):
        return FrozenList(freeze(v) for v in value)
    return value


def thaw(value: Any) -> Any:
    """A deep mutable copy: the inverse of `freeze`, for a writer that needs plain types (a YAML
    dump, a caller that edits its copy)."""
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [thaw(v) for v in value]
    return value
