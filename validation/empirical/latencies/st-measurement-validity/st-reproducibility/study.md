# reproducibility

## Background

This study checks that the data of the benchmark are reproducible. The
question of the study is in `study.yaml`. It has three parts:

1. Does the same image give the same histograms on another host?
2. Does a rebuild from the sources of the run (its snapshot or its
   commit) give the same image?
3. Does a new safety revision give the old data of the same code
   placement?

## Experiments

This study has no experiment of its own. It runs points of other
experiments again (mode `rerun`: its own runs of these experiments, not
their data):

- `wp3-irq-1m` and `wp3-wake-1m` of `kconfig-factors`.
- `t2t-load-1m` of `load-scaling/t2t-under-load`.

The re-runs on another host have no hypothesis. Their results are the
central results `same-image-same-data` and `rebuild-same-image`. A
person confirms `rebuild-same-image`, because `run.py --rebuild` writes
no record yet.

The third part reads the data of `code-place-q4` of `code-placement`
(mode `reuse`). It compares the flash points `f0` and `f4` with the
reference points `p0` and `p4` of the run
`code-layout/20261025T060257Z` (safety `5a7d0a5`). `f0` and `f4` have
the same code layout as `p0` and `p4` (commit `48f1341` of
`LATBENCH_CODE_PLACE`).

The prediction came from the study `code-placement` (criterion C3 of
`code-place-q4`). It was written on 2026-10-25, before the run
`code-place-q4/20261025T184743Z` (date from `hypotheses.yaml`):

- H1: a new safety revision reproduces the old data of the same code
  placement. The flash points `f0` and `f4` give the IRQ p50, the ISR
  to thread p50 and the drift of the reference points `p0` and `p4`.

## References

- `hypotheses.yaml`: the hypothesis H1 and its checks.
- `st-kconfig-factors/study.md`: the WP3 experiments.
- `st-load-scaling/st-t2t-under-load/study.md`: `t2t-load-1m`.
- `st-measurement-validity/st-code-placement/study.md`: `code-place-q4`
  and the reference run in flash.
