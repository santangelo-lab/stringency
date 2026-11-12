"""Read-only JSON containers for an admitted Action's values (L106).

`FrozenDict` and `FrozenList` are `dict` and `list` to `isinstance`, `json`, `jsonschema`,
`yaml.safe_dump` (representers registered below) and equality with a plain value, and refuse
every method that would change them in place, `__init__` again included. Building one freezes
everything inside it, and its keys are the strings `json` would write for them (`True` is
`"true"`, `None` is `"null"`, `1` is `"1"`), so the frozen value and its canonical JSON (the
Action's `params_hash`) always agree.

To change something, change a copy, and take it with `thaw(x)`: a deep, plain, mutable copy.
`x.copy()` and `copy.deepcopy(x)` are the same deep copy. `dict(x)` and `list(x)` are shallow,
as for any dict or list: the outer level is the caller's, and every nested value is still the
frozen one, so `dict(params)["groups"].append(...)` raises. Plugin and predicate code that edits
a parameter value uses `thaw`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any, NoReturn

import yaml

READ_ONLY = (
    "an Action's values are read-only once built (L106); change a copy from "
    "stringency.frozen.thaw(value)"
)


def _refuse(self: Any, *args: Any, **kwargs: Any) -> NoReturn:
    raise TypeError(READ_ONLY)


def json_key(key: Any) -> str:
    """The string `json.dumps` writes for a mapping key: a string as it is, `true`, `false`,
    `null`, an integer's or a float's JSON spelling. Any other key is refused, as `json` refuses
    it."""
    if isinstance(key, str):
        return key
    if key is True:
        return "true"
    if key is False:
        return "false"
    if key is None:
        return "null"
    if isinstance(key, int | float):
        return json.dumps(key)
    raise TypeError(f"a key of type {type(key).__name__} cannot be written as JSON: {key!r}")


class FrozenDict(dict[str, Any]):
    """A `dict` whose contents cannot be changed in place; built by freezing what it is given."""

    __slots__ = ()

    def __new__(cls, value: Mapping[Any, Any] | None = None, /, **kw: Any) -> FrozenDict:
        self = dict.__new__(cls)
        items: dict[str, Any] = {}
        for k, v in [*(value or {}).items(), *kw.items()]:
            items[json_key(k)] = freeze(v)
        dict.update(self, items)
        return self

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Filled by `__new__`; calling it again changes nothing."""

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

    def copy(self) -> dict[str, Any]:
        """A deep, plain, mutable copy (`thaw`)."""
        return thaw(self)  # type: ignore[no-any-return]

    def __copy__(self) -> dict[str, Any]:
        return self.copy()

    def __deepcopy__(self, memo: dict[int, Any]) -> Any:
        return thaw(self)


class FrozenList(list[Any]):
    """A `list` whose contents cannot be changed in place; built by freezing what it is given."""

    __slots__ = ()

    def __new__(cls, value: Iterable[Any] = (), /) -> FrozenList:
        self = list.__new__(cls)
        list.extend(self, [freeze(v) for v in value])
        return self

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Filled by `__new__`; calling it again changes nothing."""

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

    def copy(self) -> list[Any]:
        """A deep, plain, mutable copy (`thaw`)."""
        return thaw(self)  # type: ignore[no-any-return]

    def __copy__(self) -> list[Any]:
        return self.copy()

    def __deepcopy__(self, memo: dict[int, Any]) -> Any:
        return thaw(self)


def freeze(value: Any) -> Any:
    """A deep read-only copy of a JSON-like value: mappings become `FrozenDict` (keys as JSON
    writes them), lists and tuples `FrozenList`, everything else is kept (strings, numbers,
    booleans and None are immutable already). The caller's value is never shared with the
    result."""
    if isinstance(value, FrozenDict | FrozenList):
        return value  # built frozen all the way down
    if isinstance(value, Mapping):
        return FrozenDict(value)
    if isinstance(value, list | tuple):
        return FrozenList(value)
    return value


def thaw(value: Any) -> Any:
    """A deep, plain, mutable copy: the inverse of `freeze`. Use it to change a value taken from
    an Action, or to hand one to a writer that wants plain types."""
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [thaw(v) for v in value]
    return value


# `yaml.safe_dump` represents exact types only; a frozen value dumps as the dict or list it is
for _dumper in (yaml.SafeDumper, yaml.Dumper):
    _dumper.add_representer(FrozenDict, yaml.representer.SafeRepresenter.represent_dict)
    _dumper.add_representer(FrozenList, yaml.representer.SafeRepresenter.represent_list)
