"""L195: a judgment's rationale is read by the answer's classifier. The texts are the three
rationales of the Lyons outlier judgment (`qc2_outliers_all`, replicate 1) that
`judg.numeric_claims_match@2` blocked for `24`, `2`, `48`, `2`; `6`; and `1`, `5`, `2`."""

from __future__ import annotations

from types import SimpleNamespace

from stringency.predicates import registry
from stringency.predicates.engine.judg import rationale_numerals
from stringency.project import Project
from tests.helpers import judgment, judgment_bundle, make_ctx, ref, replicate

DESIGN = SimpleNamespace(
    factors={
        "timepoint_h": SimpleNamespace(levels=["6", "24", "48"]),
        "condition": SimpleNamespace(levels=["CLP"]),
    }
)

LIVER_NOTE = (
    "included with note: most of section missing from slide region, low total area; "
    "potential cross-contamination with 24-2 and 48-2 (manual_hist_info.md)"
)
LIVER = (
    f"Histology issue is true: {LIVER_NOTE}. Cell count 3515 is 84.5 percent below the "
    "reference centre and below the smallest earlier included liver punch (9794). The "
    "within-study band cannot speak to this: its low edge is clipped at zero on a band of five."
)
LIVER_CITED = ["true", LIVER_NOTE, "3515", "84.5", "9794", "none"]

LUNG = (
    "The decoded fraction 0.7697 is the one concerning departure: 2.0 percent below the centre "
    "of a tight band of eleven lung punches. The absolute floor is 0.6 and the value is far "
    "above it. Its sibling 6-1-Lung-A is under review; the 6 h and 48 h groups read alike."
)
LUNG_CITED = ["true", "0.7697", "2.0", "0.6", "none"]

SPLEEN_NOTE = "included with note: Lower 1/5 section of punch out of focus"
SPLEEN = (
    f"Histology issue is true: {SPLEEN_NOTE}, a focus failure. Cell count 65810.0 is low, 45.2 "
    "percent below centre at 6.3 scaled MAD. Fail fraction 0.1224 is high, 403.9 percent above "
    "centre at 9.1 scaled MAD; its sibling 6-2-Spleen-B is unaffected."
)
SPLEEN_CITED = ["true", SPLEEN_NOTE, "65810.0", "45.2", "6.3", "0.1224", "403.9", "9.1"]


def test_the_lyons_rationales_pass() -> None:
    for item, text, cited in [
        ("48-1-Liver", LIVER, LIVER_CITED),
        ("6-1-Lung-B", LUNG, LUNG_CITED),
        ("6-2-Spleen-A", SPLEEN, SPLEEN_CITED),
    ]:
        got = rationale_numerals(DESIGN, item, text, cited)
        assert got["failed"] == [], (item, got["failed"])
    # what was left unchecked is listed with its class
    got = rationale_numerals(DESIGN, "6-1-Lung-B", LUNG, LUNG_CITED)
    classes = {(e["numeral"], e["class"]) for e in got["exempt"]}
    assert ("6", "level") in classes and ("48", "level") in classes and ("6", "id") in classes


def test_a_measurement_in_a_rationale_still_needs_its_cell() -> None:
    # a value no cited cell holds, beside identifiers and levels that pass
    text = LIVER.replace("84.5 percent", "91.2 percent")
    got = rationale_numerals(DESIGN, "48-1-Liver", text, LIVER_CITED)
    assert [f["numeral"] for f in got["failed"]] == ["91.2"]
    # a numeral that is no level, no id and no count is a claim: 72 is not a level here
    got = rationale_numerals(DESIGN, "6-1-Lung-B", "the 72 h group and 3 clusters", LUNG_CITED)
    assert [f["numeral"] for f in got["failed"]] == ["72", "3"]
    # the note's numerals pass only when the note is cited
    got = rationale_numerals(DESIGN, "6-2-Spleen-A", SPLEEN, SPLEEN_CITED[2:])
    assert [f["numeral"] for f in got["failed"]] == ["1", "5"]


def test_the_predicate_is_version_3_and_lists_what_it_left(project: Project) -> None:
    p = registry.get("judg.numeric_claims_match")
    assert p is not None and p.version == 3

    def ctx(rationale: str):  # type: ignore[no-untyped-def]
        items = [
            judgment("A", "abundant", rationale=rationale),
            judgment("B", "sparse"),
            judgment("C", "variable"),
        ]
        return make_ctx(
            project, "03_label", phase="post", output=judgment_bundle([replicate(items)])
        )

    mean = ref("A", "mean_value")["value"]
    assert not p.fn(ctx(f"mean {mean} in punch ctrl-2-Spleen, as in 2025, over 4 animals")).fired
    v = p.fn(ctx(f"mean {mean} in punch ctrl-2-Spleen but I recall 80.1"))
    assert v.fired
    assert [(q["item"], q["numeral"]) for q in v.evidence["problems"]] == [("A", "80.1")]
    assert v.evidence["problems"][0]["nearest"]
    assert {"replicate": 1, "item": "A", "numeral": "2", "class": "id"} in v.evidence["not_checked"]
