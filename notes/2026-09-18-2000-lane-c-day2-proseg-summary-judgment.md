# Lane C day 2: Proseg route delivered, cross-region summary, first judgment on real data

## Goal

Finish `xenium-qc` on the four Proseg tissues, build the cross-region QC summary and the outlier
judgment the owner asked for, and make progress visible in the session. Data-side log:
`/lab/projects/Lyons_CLP/PROGRESS.md`; running tooling log: `spec/plans/lane-c-day1-2026-09-17.md`.

## Done

- Xenium Ranger: the BMESEQ image was an early 4.0.1 build (4.0.1.1); the 2026-08-13 build
  (4.0.1.4) reads XOA 4.0.2 bundles. Rootless image recipe (`envs/xeniumranger/xeniumranger.def`:
  entries copied, symlinks recreated in `%setup`). Direct import verified on the real lung.
- Two pipeline fixes on `jrose835/Xen_Segmentation_NextFlow` dev (`cca9feb`): the clamp step
  writes a real bundle (hard links or copies), and can drop `experiment.xenium` keys.
- Method `stringency-xenium-method`: `xenium-resegment` (its own project per region; QC binds
  the delivered bundle via `derived_from`), stable per-sample Nextflow launch dir so `-resume`
  survives runs; `xenium-qc-summary` (eight named table inputs); `xenium-qc-outliers` (judgment
  module `flag_outlier_punches`, three replicates, negative and positive controls, flag hold);
  delivery skills `skills/<pipeline>.yml`. Tags v0.3.0-rc6, v0.3.1-rc2, v0.3.2-rc2.
- Plugin `stringency-singlecell` 0.1.7 (tag v0.1.10): `qc_summary` question, `qc_metrics_table`
  type, judgment operation and vocabulary, `punch` as an observation unit.
- Engine (branch `lane-c-directory-inputs`): `init.column_missing` skips `derived_from` inputs;
  `board` and `present` verbs; dispatch suffix names the `{nonce, reported, structured}` envelope
  and the parser accepts the flat shape.
- Delivered: all eight regions QC'd; four resegmentations; the cross-region summary. The outlier
  proposal (unanimous, 3 exclude / 6 review) is at its flag hold for the owner.

## Learned

- Proseg 16 threads: lungs 4.5 h at 42 to 53 GB, guts 6 to 7.5 h at 87 to 97 GB; memory
  triples in the final phase. `systemd-run --user --scope -p MemoryMax -p MemorySwapMax=0` caps
  a job for real; Nextflow refuses a process whose declared memory exceeds the cgroup.
- Nextflow clears the environment before `apptainer exec` (binds must be in config), keeps its
  resume cache in the launch directory, and `%files` in apptainer defs dereferences symlinks.
- A pinned project cannot follow a pipeline fix (`param.locked_changed`): the design working;
  cost is a re-declaration and a hold.
- Judgment dispatch on real data surfaced: envelope mismatch (fixed), one hold per item on
  invalid replicates (Lane A), the numeric-claims check catching rule constants written as
  digits (module prompt should say "in words"), no per-item amendment at a hold (Lane A).
- Presentation: the owner wants progress and results IN the session; `board` and `present`
  exist for that and the operator skill says so (section 7).

## Altered

Chained projects replace the three-step Proseg pipeline (`xenium-qc-proseg` superseded).
Spleen thresholds revised for this panel. Split pre-filter off on every run. Roadmap Lane A gains
item 5 (holds that ask the right question) and the engine gaps list.

## Open

1. Owner decides the exclusion hold `01M2V2JRJ0ZY6FC9PR8QE1AZY3` in `qc_outliers_all`.
2. Engine PR from `lane-c-directory-inputs`; delete the broken tags; Lane A item 5.
3. Module prompt: rule constants in words; proposal CSV should carry evidence and rationale.
4. Track 3 next: clustering and annotation modules on the QC objects.

## Verify

```bash
stringency board /lab/projects/Lyons_CLP
cd /lab/projects/Lyons_CLP/qc_outliers_all && stringency present --hold 01M2V2JRJ0ZY6FC9PR8QE1AZY3 --skills-dir ~/github/stringency-xenium-method/skills
```
