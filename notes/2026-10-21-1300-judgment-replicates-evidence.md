# Judgment replicates: what the literature says (2026-10-21)

## Goal

The owner asked whether published research supports or refutes the premise behind judgment
steps: that several independent agents make a subjective call better, or more certain, than one.
A literature search only; no engine change.

## Done

- Read design 3.5, 8.4, 10.1 and `spec/plans/judge-sources-plan.md` to pin down what a
  judgment step does: N replicates of one model, one rendered prompt, fresh contexts, no
  interaction between replicates, no majority vote, any split or abstention held for a person.
- Searched the literature on four questions: multi-agent debate against single-agent baselines
  at matched compute; correlated errors and sample consistency as an uncertainty signal; LLM
  cell-type annotation with consensus; routing uncertain LLM labels to people. The key arXiv
  abstracts (export API) and the PMC pages of Hou & Ji 2024, AnnDictionary 2025 and CASSIA 2025
  were checked directly. The mLLMCelltype DOI resolves to Communications Biology.

## Learned

- The design is not a multi-agent debate system, so the debate literature mostly does not apply
  to it. Where it does apply, it favours the design: at matched compute, the gains credited to
  debate come from independent sampling and voting, and agents that interact switch from
  correct to incorrect answers (Choi, Zhu & Li 2025, arXiv 2508.17536; Wynn, Satija & Hadfield
  2025, arXiv 2509.05396; Tran & Kiela 2026, arXiv 2604.02460).
- Disagreement among replicates is a well-supported signal of error:
  - Semantic entropy (Farquhar et al. 2024, Nature).
  - Sample-consistency calibration (Lyu et al. 2024, arXiv 2402.13904).
  - CASSIA: consensus similarity across runs had a median of about 90 for correct labels and
    about 60 for incorrect ones.
  - Answering only when 3 runs agree gave 87-88% accuracy at 54-62% coverage (Mehta 2026,
    arXiv 2602.11619).
  - Sending order-unstable items to a person raised a GPT-4 judge's accuracy from 52.7 to 73.8
    (Wang et al. 2024, ACL).

  "The dissent is the information" (8.4) holds up.
- Agreement is the weak half:
  - Replicates of one model with the same prompt are unanimous on errors the model makes
    consistently. Such errors are not rarer in larger models, and sampling-based detectors miss
    them (Tan et al. 2025, arXiv 2505.17656).
  - The semantic-entropy authors state the same limit.
  - Across different models, when two are both wrong they give the same wrong answer about 60%
    of the time (Kim et al. 2025, ICML, arXiv 2506.07962).
  - Nine frontier judges carried about 2 votes' worth of independent information (Kohli 2026,
    arXiv 2605.29800).
  - The rate at which all members are wrong together caps what any vote or router can achieve
    (Chen 2026, arXiv 2606.27288).

  Fresh contexts give isolation (10.1), not independent errors.
- Cell annotation:
  - GPT-4 gave the same label on repeat in 85% of cases (Hou & Ji 2024).
  - A plurality vote over many LLMs scored 80.5% against 84.0% for the best single model
    (AnnDictionary, Nat Commun 2025).
  - mLLMCelltype reports 77.2% against 61.5% for a single-LLM baseline (Commun Biol 2026).
  - Multi-model consensus helps in some studies and not in others. The more consistent finding
    is that agreement across runs separates correct labels from incorrect ones.
- Verbalized confidence is overconfident and weak (Xiong et al. 2024, ICLR). This supports K2's
  demotion of `any_low` to a note.
- Ways to decorrelate replicates, strongest first:
  1. Rephrase the question or perturb the prompt (SAC3, arXiv 2311.01740; CoAnnotating, EMNLP
     2023).
  2. Use a second model family.
  3. Shuffle the order of items or options (position bias: Wang et al. 2024; Shi et al. 2025).
  4. Raise the temperature. This has little effect, and under dispatch the engine does not set
     temperature anyway.

## Altered

Nothing.

## Open

Proposals for the owner, none started:

1. Measure the unanimous-but-wrong rate per module: in positive controls, accuracy on unanimous
   items separately from held items. The judgments and consensus tables already hold the data.
2. Per-replicate prompt perturbation, such as a different item order under `all_items` or a
   different vocabulary order. The prompt would then be per replicate, not per step, which
   touches 3.5 step 3 and the prompt hashing.
3. Weigh judge-sources S4 (a mixed panel) against this evidence. Under a unanimity rule a weaker
   second family cannot lower the quality of agreed labels; it can only raise the hold rate.
4. Optionally sign off a random sample of agreed items, the confidence-driven inference
   pattern (Gligoric et al. 2025, NAACL).
5. The methods paragraph in design 13 says "three independent replicates per cluster".
   "Independent" claims more than the evidence supports; "in separate contexts" is accurate.
