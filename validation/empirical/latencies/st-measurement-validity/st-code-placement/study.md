# code-placement

## Background

This study measures how much the address of the code changes the
latency. The question of the study is in `study.yaml`: which placement
gives numbers that a comparison between trees and options can use?

In `wake-threads-1m`, the same code with different array sizes gave two
groups: IRQ p50 86 or 82 cycles, clock drift 9.7 or 8.0 cycles per
wake. The difference between the trees in the ISR to thread p50 changed
from 0 to 190 cycles from build to build. The code of these builds
starts at different addresses (`_isr_wrapper` at 0x...1870, 0x...1910,
0x...1904).

The study moves the code with a pad. `LATBENCH_CODE_PAD_BYTES` sets the
pad. `common/src/pad.c` moves all app and kernel code by this number of
bytes. Nothing else changes. The choice `LATBENCH_CODE_PLACE` selects
the place of the code. The study uses two of its values:

- `LATBENCH_CODE_FLASH_PAD`: the code is in flash, with the pad.
- `LATBENCH_CODE_RAM`: the hot code is in RAM. On `nucleo_g474re`, this
  is the CCM SRAM. The pad moves only the relocated code. Code in the
  CCM SRAM does not go through the flash and its cache.

The choice `LATBENCH_CODE_PLACE` came after the run
`code-layout/20261025T060257Z` (commit `48f1341`). Since then, the pad
needs `LATBENCH_CODE_FLASH_PAD`. The run had no choice, but the code
layout of each point is the same. The flash layout of `f0` and `f4` in
`wake-code-place-q4` is that of `p0` and `p4` in `wake-code-layout`.

## Experiments

`wake-code-layout` measures how much the place of the code in flash changes
the latency. It moves the code in steps of 4 bytes over 32 bytes, on
the tree `ws-safety`. Its run `code-layout/20261025T060257Z` (safety
`5a7d0a5`, 200000 samples, pads 0..28) is the reference in flash. In
this run, the spread over the pads was (values from the basis texts of
`hypotheses.yaml`):

- IRQ p50: 5 cycles (81..86).
- Drift per wake, anchor `default`: 1.6 cycles (8.06..9.66).
- ISR to thread p50, anchor `default`: 40 cycles (1663..1703).
- ISR to thread p50, anchor `noslice`: 35 cycles (763..798).

`wake-code-place-q4` asks: does hot code in RAM remove the effect of the code
address on the latency? This is question Q4 of the review of
2026-10-25 (items L2 and L17 of `later.md`). The decision to check:
comparisons between trees and options use `LATBENCH_CODE_RAM`. Absolute
numbers use `LATBENCH_CODE_FLASH_PAD`, as a range over the pads. The
flash points are the control. The checks read the p50 of each histogram
(`irq`, `isr2thr`) and the drift per wake (`clock_drift_cyc` / samples,
default anchor only).

`wake-code-place-q4` has 50000 samples per point. The p50 of these
histograms and the drift per wake do not change with the number of
samples. In `wake-clock-drift-layout`, 200000 against 1000000 samples
changed the drift by 0.01 cycles per wake. Thus 50000 samples are
sufficient. The board time is about 35 s per point, with build and
flash.

`wake-code-place-q4-up` is the second part of the check. It asks: does hot
code in RAM remove the difference between the trees that changes from
build to build? It has the points of `wake-code-place-q4` that the tree
comparison needs, on the tree `ws-up`. The tree difference is the value
of `ws-up` minus the value of `ws-safety` (`wake-code-place-q4`) at the same
point.

The study imports `wake-stim-seed-1m` from
`measurement-validity/stimulus-sampling`. Its default seed checks a
shift of the CCM code by 16 bytes (H2 k). The shift comes from a new
`LAT META` line in `stim_init()`.

The predictions were written before the runs (dates from
`hypotheses.yaml`):

- H1 (2026-10-25, before `code-layout/20261025T060257Z`): the latency
  and the drift change with the pad, with a period of the flash line or
  of the cache line.
- H2 (2026-10-25, before `code-place-q4/20261025T184743Z` and
  `code-place-q4-up/20261025T185845Z`, and 2026-10-26, before
  `stim-seed-1m/20261026T155715Z`): hot code in the CCM SRAM removes
  the effect of the code address. The pad, the build of another tree
  and a shift of the CCM code do not change the latency and the drift.

The criteria of the old file map to the checks as follows. C1 (the pad
in RAM) is H2 a..e. C2 (the tree difference is the same at `r0` and at
`r4`) is H2 f..j. C3 (the new revision against the old flash data) is
H1 of the study `reproducibility`. C4 (the cost of RAM) has no limit:
it is the central result `ram-cost`. The log checks of `wake-code-place-q4`
and `wake-code-place-q4-up` are acceptance checks in their `experiment.yaml`
files.

## References

- `hypotheses.yaml`: the hypotheses H1 and H2, and their checks.
- `ex-code-layout/experiment.md`: the pad in flash.
- `ex-code-place-q4/experiment.md`: the pad in RAM and the flash
  control.
- `ex-code-place-q4-up/experiment.md`: the same points on `ws-up`.
- Run `code-layout/20261025T060257Z` (safety `5a7d0a5`): the reference
  in flash.
- The commit of `LATBENCH_CODE_PLACE` (`48f1341`): the flash layout of
  `f0` and `f4` is that of `p0` and `p4`.
- `st-load-scaling/st-timeout-queue-cost/ex-wake-threads-1m/experiment.md`:
  the two groups of builds.
- `st-measurement-validity/st-clock-drift/ex-clock-drift-layout/experiment.md`:
  the drift with 200000 and 1000000 samples.
- `st-measurement-validity/st-reproducibility/study.md`: the check of
  the old flash data.
- Review of 2026-10-25, question Q4, and `later.md`, items L2 and L17.
