# Annotation controls: the fine label and the fraction expressing

**Status 2026-10-23.** Rows L110 to L112 of `PLAN.md`, items 3.15 to 3.21 of the Xenium
method's `PLAN.md`. Built: `sc.fine_label_uncited@1` in plugin singlecell 0.8.5 (not tagged).
The owner chose both designs for one fine label of three (section 4). The rest is filed. The owner's points of 2026-10-23, checked against the Xenium method at
`v0.6.0-rc19` (`531af60`), the engine at `f6041d2` and plugin singlecell 0.8.4 (`e437488`). The
measurements are on the annotation control's ROSC liver fixture; the Lyons data is not reachable
from the machine this was written on, so gut cluster 9 is the owner's reading and has not been
re-examined here.

The owner's points:

1. The fine label needs more control. Lyons CLP gut cluster 9 was labelled enterocyte with the
   fine label "IFN/stress", and the state does not hold up on closer reading; part of the cause may
   be individual markers read in place of whole gene sets.
2. The fraction of the cluster's cells expressing a marker, and above all its difference from the
   fraction of all other cells (`pct_diff`), must weigh in the annotation.
3. (Later the same day.) The fine label stays one free-text string: experiments differ too much
   for it ever to be picked from a preset list. Gene-set states are evidence for writing it, not
   its vocabulary. Taking the first of three reviewers' fine labels is arbitrary.
4. (Later still.) Of the ways to make one fine label of three, both: the deterministic agreement
   on claims, and a second judgment that chooses among the candidates of the clusters it leaves
   contested.

## 1. What the code does today

**The fine label is the method's field, end to end.** The engine has no code that names it.

- `annotate-clusters/schema.json` declares `fine_label` as a string or null of at most eighty
  characters. `prompt.md` asks for it in three cases: a state of a known type (a cluster that is
  one time point), the type an `unknown` cluster's markers show, and a subtype the vocabulary
  keeps coarse (endothelial).
- Until 0.8.5 nothing checked it but the schema: `judg.numeric_claims_match` reads `rationale`
  only, `judg.vocabulary_resolves` reads `label` only.
- The engine writes every valid replicate's records to `judgments.jsonl` and leaves the field out
  of `consensus.json`; agreement is on `label` alone, so three replicates that agree on
  `enterocyte` with three different fine labels are agreed and nothing is held.
- `apply-labels/pre.R` keeps, per cluster, the first non-empty fine label in `judgments.jsonl`
  whose label equals the consensus label. A person's choice at a hold (`review.choose` records
  accept with the first replicate that called the label) is not read; an override carries only
  `label` and `ontology_id`, and `choose` writes it without the id, so the cluster's id is null.

**The fraction expressing is present but carries no weight.**

- `find-markers` writes `pct_in`, `pct_out` (Seurat's `pct.2`, the fraction of all cells outside
  the cluster with a count) and `pct_diff` per marker, and the fraction expressing every gene in
  every cluster.
- `markers_top` and the item's `top_markers` rank by `avg_log2FC`. On the ROSC liver fixture 191
  of the 500 `markers_top` rows (38 percent) have `pct_diff` below 0.2, 259 have `pct_in` below
  0.3, and in four of the twenty clusters at least half of the ten genes in `top_markers` have
  `pct_diff` below 0.2.
- `canonical_markers` scales each gene's mean to its across-cluster maximum and shows `pct_<c>`
  but not the rest-of-organ fraction or the difference. `lineages_high`, which the prompt reads
  for doublets, counts a gene on the scaled mean alone: of the 70 canonical cells at 0.7 or above
  with a marker row, 38 have `pct_diff` below 0.2, at both ends (`Cd209a` in 0.018 of cluster
  12's cells; `Apoa1` in 0.999 of cluster 5 against 0.929 elsewhere).
- A gene canonical for two lineages counts toward the first row's only (`Mki67` epithelial in gut,
  lymphoid in spleen; `Kit` stromal in gut; `Vcam1` stromal in spleen).
- The positive fixture holds the fraction expressing only where the archive had a marker row: 473
  of its 1,040 canonical `pct_<c>` cells read `na`.

## 2. What is proposed

**A. The fraction expressing as evidence (method 3.15; no engine or plugin change).**
`annotate-clusters` 0.3.0 `pre.py` adds `pctout_<c>` and `pctdiff_<c>` to `canonical_markers`
(from `cluster_pct_expressing.csv` and the cluster sizes, Seurat's definition). `markers_top`
ranks by `pct_diff` among the positive markers, the fold-change rank kept as a column, and
`top_markers` follows it. `n_specific_markers` (log fold change at least one half and `pct_diff`
at least the floor) and `lineages_high` counting a gene only at scaled mean seven tenths and
`pct_diff` at the floor, a shared gene counting for every lineage it argues for. The prompt's first
reading step names `pct_diff`. `judgment.must_cite` names `cluster_summary.n_specific_markers` and
`cluster_summary.lineages_high` (it binds cells in rows keyed by the item). Floor 0.2 to start, set
on the Lyons deliveries.

**B. States from whole gene sets, as evidence for the fine label (method 3.16).** `find-markers`
0.2.0 scores every cell on each programme of section 3 with UCell (the method has the code in
`_rlib/pathway_utils.R` for `score-pathways`). Per cluster and programme: the mean score, its rank
among the clusters **of the same lineage** (an acute-phase programme compared organ-wide only finds
the hepatocytes), the fraction of the cluster's cells above the organ's ninetieth percentile
against the same fraction in its sibling clusters, and how many of the programme's panel genes
have `pct_diff` at or above the floor. That last count is the breadth the owner asks for: a state
read from two interferon genes in a tenth of the cells is what the table must make visible. A
table `state_programmes`, keyed by cluster with columns per programme, goes to the reviewers; the
prompt says a fine label that names a state cites that programme's cells. The fine label stays the
reviewers' text.

**C. Checks on the fine label's text (plugin, L111).** Built: `sc.fine_label_uncited@1` flags a
gene a replicate's fine label names that its record does not cite for its own cluster. Words that
are not gene symbols ("IFN", "stress") pass it. Their twin waits on B: with an alias table shipped
beside the programmes (each programme's words: "interferon", "IFN", "ISG"), a fine label that
names a programme must cite its `state_programmes` cell for the cluster, and the cell must clear
the programme's call. The plugin reads the aliases from the step's evidence tables, as it reads
genes, so it keeps no list of its own.

**D. From three fine labels to one (method 3.17 and 3.21; the owner chose both designs).** A
deterministic step settles the clusters whose reviewers' claims converge; a second judgment
chooses among the candidates of the rest. Section 4.

**E. A person's choice reaches the cells (engine L110, method 3.18).** The consensus output gains,
per item, the replicate a person chose (`chosen_replicate`, on accept) and the review's whole
correction (`correction`, on override), read from `reviews` by `review_id`; `_validate_correction`
validates the module's own fields against its schema instead of dropping them. `apply-labels`
0.2.0 reads both first (section 4 gives the whole order), fills a null ontology id from
`annotate-clusters/cell_types_mouse.csv`, and lists every replicate's fine label in
`label_summary`.

**F. Controls (method 3.19).** The positive fixture rebuilt from a Lyons delivery's
`cluster_evidence`, which has the whole fraction-expressing table. State controls on B's table:
positive on the synthetic annotated object's planted interferon module (24 h macrophages),
negative on gut cluster 9 once the owner's reading of it is written down. A fine-label control for
D: a fixture where the three replicates' fine labels agree, one where they split.

## 3. State programmes (candidates for the owner)

Response genes, not pathway members: a receptor, kinase or transcription factor is expressed at
rest and dilutes a score. Each list is to be checked against the panel with the method's
`validate_genesets` on a Lyons object before it is used, as the shipped innate modules were; the
panel list is not on the machine this was written on, so coverage below is not claimed.

| programme | genes (mouse) | read within | note |
|---|---|---|---|
| `ifn_type1_response` | Isg15, Ifit1, Ifit2, Ifit3, Ifi44, Rsad2, Oasl1, Oasl2, Oas1a, Mx1, Mx2, Irf7, Usp18, Bst2, Rtp4, Ifi27l2a, Cmpk2, Xaf1 | every lineage | the response half of the shipped `ifn_isg`, which also carries receptors and kinases |
| `ifn_gamma_response` | Cxcl9, Cxcl10, Gbp2, Gbp5, Gbp7, Iigp1, Igtp, Irgm1, Tgtp1, Ido1, Ciita, Cd274, Irf1, Ubd | every lineage | separates a type II response (T and NK cells nearby) from a type I one |
| `tnf_nfkb_response` | Nfkbia, Nfkbiz, Tnfaip3, Tnfaip2, Zc3h12a, Birc3, Icam1, Cxcl1, Cxcl2, Ccl2, Il6, Socs3, Ier3, Relb | every lineage | the targets, in place of the shipped `nfkb_cytokines` pathway list |
| `acute_phase` | Saa1, Saa2, Saa3, Orm1, Orm2, Apcs, Hp, Lcn2, Lbp, Serpina3n, Fga, Fgb, Fgg, Cebpd | hepatocytes; epithelium for Saa3 and Lcn2 | lineage-bound; organ-wide it marks hepatocytes, not a state |
| `immediate_early` | Fos, Fosb, Jun, Junb, Egr1, Egr2, Egr3, Atf3, Ier2, Ier5, Nr4a1, Nr4a2, Dusp1, Klf2, Klf4, Zfp36, Btg2, Ppp1r15a | every lineage | in fixed tissue a stimulus in vivo or warm ischaemia before fixation, not dissociation; the "stress" a reviewer may mean |
| `heat_shock` | Hspa1a, Hspa1b, Hsph1, Hspa8, Hsp90aa1, Dnajb1, Dnaja1, Hspb1, Hspd1, Hspe1, Bag3, Chordc1 | every lineage | proteotoxic stress; often beside `immediate_early` |
| `er_stress_upr` | Hspa5, Ddit3, Atf4, Xbp1, Herpud1, Sdf2l1, Manf, Dnajb9, Pdia4, Pdia6, Hyou1, Creld2, Trib3, Asns | every lineage; plasma and acinar cells carry it at rest | |
| `hypoxia` | Vegfa, Slc2a1, Pgk1, Ldha, Bnip3, Adm, Egln3, Ndrg1, Ankrd37, P4ha1, Pdk1, Ero1a, Ddit4, Hk2, Pfkfb3 | every lineage | |
| `oxidative_nrf2` | Hmox1, Nqo1, Gclc, Gclm, Txnrd1, Srxn1, Slc7a11, Sqstm1, Prdx1, Mt1, Mt2 | every lineage | Hmox1 is also a red pulp macrophage marker |
| `glucocorticoid` | Tsc22d3, Fkbp5, Per1, Zbtb16, Sgk1, Klf9, Errfi1, Cdkn1a | every lineage | the corticosterone surge of sepsis; shares Dusp1-type genes with `immediate_early`, so kept apart |
| `p53_damage` | Cdkn1a, Mdm2, Bax, Bbc3, Gadd45a, Phlda3, Ccng1, Eda2r, Zmat3, Trp53inp1, Aen, Sesn2, Pmaip1 | every lineage | |
| `cycling_s`, `cycling_g2m` | the shipped cell-cycle lists | every lineage | already in `score-pathways` |
| `endothelial_activation` | Sele, Selp, Icam1, Vcam1, Lrg1, Angpt2, Esm1, Ptx3, Ackr1, Cxcl1 | endothelial | Vcam1 is a red pulp macrophage marker too |
| `hepatic_fasting` | Pck1, G6pc, Ppargc1a, Angptl4, Cpt1a, Hmgcs2, Fgf21, Cyp4a14, Acot1, Pdk4, Igfbp1 | hepatocytes | the PPAR-alpha programme of septic anorexia |
| `gut_antimicrobial` | Reg3b, Reg3g, Lcn2, Saa1, Saa2, Nos2, Duox2, Duoxa2, Lypd8, Retnlb | intestinal epithelium | Paneth lineage genes (Lyz1, Defa) left out |
| `gut_regenerative` | Clu, Ly6a, Anxa1, Anxa3, Tacstd2, Basp1, Spp1, Msln | intestinal epithelium | revival and fetal-like repair states after injury |
| `lung_transitional` | Cldn4, Sfn, Lgals3, Krt19, Areg, Itgb6, Tnfrsf12a, Cdkn1a | alveolar epithelium | Krt8, the usual marker, is not on the panel (guide section 3) |
| `neutrophil_activation` | Il1b, Acod1, Clec4d, Clec4e, Cxcl2, Ccl3, Ccl4, Ptgs2, Nlrp3 | neutrophils, monocytes | the vocabulary's own note on activated neutrophils |
| `cytotoxic` | Gzma, Gzmb, Prf1, Ifng, Ccl5, Klrg1 | T and NK cells | the vocabulary's own note; Nkg7 is not on the panel |

A gene in a programme that is also a canonical marker of the cluster's lineage is scored with it
but not counted toward the breadth, so a lineage cannot read as a state.

## 4. From three fine labels to one (decided 2026-10-23: both)

Taking the first is arbitrary, a vote on free text is impossible, and a second judgment that
writes one synthesis has the same problem one step later (three replicates write three
syntheses; every profile's `replicates_min` is three). The text cannot be compared, but its
claims can: the genes it names (as `sc.fine_label_uncited` finds them) and, once B is built, the
programmes it names. The owner chose both of the ways that use this: a deterministic step settles
the clusters whose claims converge, and a second judgment, which chooses and never writes,
settles the rest. The deterministic step alone would land every contested cluster on a person;
the choosing judgment alone would dispatch for every cluster, including those whose reviewers
already agree.

**The flow in `xenium-upstream` 0.7.0.** Two steps after `08_annotate`; the later steps move up.

| step | module | kind | does |
|---|---|---|---|
| `08_annotate` | `annotate-clusters` 0.3.0 | judgment | as today, with A and B's evidence |
| `09_reconcile_fine_labels` | `reconcile-fine-labels` 0.1.0 (new) | deterministic, xenium-py | settles each cluster's fine label from its reviewers' claims, or names it contested |
| `10_choose_fine_labels` | `choose-fine-label` 0.1.0 (new) | judgment, xenium-py | items are the contested clusters only; chooses among their candidates or `none` |
| `11_apply_labels` | `apply-labels` 0.2.0 | deterministic | the labels and the settled fine labels onto the cells |
| `12_report` | `upstream-report` 0.4.0 | deterministic | says, per cluster, where its fine label came from |

**`09_reconcile_fine_labels`.** Inputs: `08`'s `judgments` and `consensus`, `07`'s
`cluster_evidence`. The judgment step does not publish the tables its reviewers cited (the engine
writes only the `judgments` and `consensus` outputs of a judgment module), so the code that builds
them moves from `annotate-clusters/pre.py` to `_pylib/annotation_evidence.py`, and both modules
build them from the same directory with the same code. Per cluster with a settled label:

1. The candidates are the fine labels of the valid replicates whose label is the consensus label;
   another type's fine label describes another type.
2. Each candidate is read into claims: genes (the recognition rule of `sc.fine_label_uncited`:
   symbols from the evidence tables, a token with a digit regardless of case, a hyphenated token
   part by part), programmes (by the aliases shipped beside the programmes, after B), and the
   remaining content words, lower-cased, without the label's own words.
3. A gene or programme claim is supported when the cluster's evidence carries it: the gene's
   `pct_diff` at the floor with a positive fold change, the programme over its call. A claim
   stands when at least `min_reviewers` (a parameter, 2 by default) of the candidates make it and
   it is supported.
4. A candidate is clean when every gene and programme claim it makes stands. The fine label is
   the clean candidate that covers the most standing claims; ties go to the most words shared
   with the other candidates, then to the most supported claims, then to the text's sort order:
   never to the replicate number. Source `agreed`.
5. No candidate at all (every reviewer left it empty): no fine label, source `none`. Otherwise,
   when no candidate is clean or no claim stands (one reviewer alone named a type for an
   `unknown` cluster, say), the cluster is contested: source `contested`, and a row in the
   `contested` table for step 10.

Outputs: `fine_labels` (cluster, fine label, source, standing claims, every candidate, every
replicate's fine label), `fine_label_claims` (cluster, replicate, claim, kind, supported), and
`contested` (cluster, `candidate_a` to `candidate_c`, equal texts merged, ordered by supported
claims and then text, never by replicate).

**`10_choose_fine_labels`.** A judgment whose `items_from` is `contested`. Its `pre.py` reads each
candidate's claims against this cluster's evidence afresh (not against who cited what in step 08,
so a control can move a text to another cluster), and writes a `candidates` table keyed by
cluster: each candidate's text, claims, supported and unsupported claims, and the cluster's
`pct_diff` and programme cells for every claimed gene and programme. The vocabulary
`fine_label_choice@1` (plugin) is positional and static: `candidate_a`, `candidate_b`,
`candidate_c`, `none`. The prompt: choose the candidate every claim of which this cluster's
evidence supports, the narrower when two are; `none` when each carries an unsupported claim; never
write a new text. Three replicates under the policy's agreement; disagreement is the engine's item
hold, where a person chooses a candidate or `none` on the console as for any label. The engine
reorders rows and vocabulary per replicate (L83), which spreads position bias. `must_cite` names
the `candidates` columns of unsupported claims. When nothing is contested the step has no items:
engine row L112.

**`11_apply_labels`, the order.** A person's correction or choice carried by L110 (at step 10's
hold an override may carry `fine_label_text`, the one way a person writes their own words), then
step 10's consensus (`candidate_x` to its text through `contested`; `none` to no fine label),
then step 09's `agreed`, else none. `label_summary` adds `fine_label_source` and every replicate's
fine label; `cell_type_fine` is the label when there is none.

**What it needs outside the method.** Engine: L112 (a judgment with no items completes without a
dispatch) and L110 (a person's choice and correction through `consensus.json`). Plugin (L111): the
operations `reconcile_fine_labels` and `choose_fine_label`, the vocabulary
`fine_label_choice@1`, and the programme-word check after B. Controls: for step 09, fixtures
where the candidates agree, split, and where one reviewer alone names a type; for step 10, a
positive (one candidate supported, the others carrying an unsupported gene; truth that candidate)
and a negative (candidate texts permuted across clusters with `shuffle_column`; truth `none`).

## 5. Contract impact

| row | what it touches | level |
|---|---|---|
| 3.15 | `annotate-clusters` 0.3.0: pre-script, prompt, `must_cite`, gates to `judg.numeric_claims_match@2` | method |
| 3.16 | `find-markers` 0.2.0: programme scores, an output table, resources | method |
| 3.17, 3.21 | `reconcile-fine-labels` 0.1.0 and `choose-fine-label` 0.1.0 (new modules), `_pylib/annotation_evidence.py`, `xenium-upstream` 0.7.0 (two steps, the later ones renumbered; skills and hold views follow) | method |
| L111 | `sc.fine_label_uncited@1` (built, 0.8.5); the programme-word check after 3.16; operations `reconcile_fine_labels` and `choose_fine_label`; vocabulary `fine_label_choice@1` | plugin |
| L110 | `consensus.json` gains two fields per item; `reviews` already stores the whole correction | engine output, additive; no trace table changes |
| L112 | a judgment step with no items completes without a dispatch | engine behaviour; design 3.5 is silent, so a DECISIONS entry |
| 3.18, 3.19 | `apply-labels` 0.2.0, `upstream-report` 0.4.0; fixtures and controls | method |

## 6. What is not proposed

- A preset list of fine labels or states (the owner, 2026-10-23).
- Splitting the fine label into fields (the owner, 2026-10-23: one string).
- An engine-level agreement rule for a judgment's free-text fields: `consensus` agrees on `label`
  alone (design 8.4). D works in the method and the plugin; an engine rule waits until a second
  module needs one.
- A judgment that writes one synthesis of the three fine labels: its own three replicates would
  write three.
- A judgment step publishing the evidence tables its reviewers cited as an output: the shared
  `_pylib` code rebuilds them from the same directory, which needs no engine change; worth an
  engine row if a third module wants them.
- `when:` on an earlier output's row count, in place of L112: more surface for one case.
