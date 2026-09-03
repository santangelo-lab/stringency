import pytest

from stringency.exit_codes import ConfigError
from stringency.pipelines import ParamDecl, Pipeline, Ref


def _pipe(steps: list[dict]) -> Pipeline:
    return Pipeline.model_validate(
        {"pipeline": 1, "name": "p", "version": "0", "domain": "d", "steps": steps}
    )


def test_refs_parse() -> None:
    r = Ref.parse("$inputs.tma_counts")
    assert r.kind == "inputs" and r.name == "tma_counts"
    r = Ref.parse("$steps.01_qc.object")
    assert (r.kind, r.name, r.output) == ("steps", "01_qc", "object")
    with pytest.raises(ConfigError):
        Ref.parse("$steps.01_qc")
    with pytest.raises(ConfigError):
        Ref.parse("inputs.x")


def test_order_is_topological_with_file_order_tiebreak() -> None:
    p = _pipe(
        [
            {"id": "c", "module": "m@1", "inputs": {"x": "$steps.a.o"}},
            {"id": "a", "module": "m@1", "inputs": {"x": "$inputs.raw"}},
            {"id": "b", "module": "m@1", "inputs": {"x": "$steps.a.o"}},
        ]
    )
    assert p.order() == ["a", "c", "b"]
    assert p.downstream("a") == ["c", "b"]


def test_cycle_and_dangling_refs_rejected() -> None:
    with pytest.raises(ValueError, match="unknown step"):
        _pipe([{"id": "a", "module": "m@1", "inputs": {"x": "$steps.zz.o"}}])
    with pytest.raises(ValueError, match="cycle"):
        _pipe(
            [
                {"id": "a", "module": "m@1", "inputs": {"x": "$steps.b.o"}},
                {"id": "b", "module": "m@1", "inputs": {"x": "$steps.a.o"}},
            ]
        )


def test_param_declarations() -> None:
    p = _pipe(
        [
            {
                "id": "a",
                "module": "m@1",
                "params": {
                    "min": {"default": 10, "range": [0, 40]},
                    "method": {"default": "bh", "options": ["bh", "none"]},
                    "seed": 7,
                },
            }
        ]
    )
    s = p.step("a")
    assert s.params["seed"] == ParamDecl(default=7)
    assert s.params["seed"].fixed
    assert s.params["min"].in_range(40) and not s.params["min"].in_range(41)
    assert s.params["method"].in_range("bh") and not s.params["method"].in_range("bonferroni")
    assert s.defaults() == {"min": 10, "method": "bh", "seed": 7}
    with pytest.raises(ValueError, match="not both"):
        _pipe(
            [
                {
                    "id": "a",
                    "module": "m@1",
                    "params": {"x": {"default": 1, "range": [0, 1], "options": [1]}},
                }
            ]
        )
