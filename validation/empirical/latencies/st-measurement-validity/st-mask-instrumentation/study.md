# mask-instrumentation

## Background

This study checks the instrument of the study `mask-time`: the interrupt
mask hooks (M4) of the tree `ws-up-irqoff`. The question of the study is
in `study.yaml`: do the hooks measure the mask time of each call site,
and do they leave the image unchanged when they are off?

The hooks must not change the code when they are off
(`CONFIG_ARM_IRQ_MASK_HOOKS=n`). Only then is a latency of
`ws-up-irqoff` without hooks also a latency of `ws-up`.

When the hooks are on, the latency histograms are not data. The hooks
make each mask section longer, and they add time to the wake path. Each
log says so (`LAT META m4=1`, `m4_note`). The analysis uses the M4
tables (`scripts/benchmarks/m4.py`) only. The IRQ tail of the same run
is only a cross check.

This study checks the instrument only. The predictions of `wake-m4-validate`
about the kernel (the timeout walk, the SysTick ISR body, the sites
without load) are checks in the study `mask-time`, which imports
`wake-m4-validate`.

## Experiments

`wake-m4-image-check` is a build check, with no board run. It builds two
points of `wake-timers-1m` on `ws-up` and on `ws-up-irqoff`, with the
hooks off. Then it compares the two images of each point. The version
strings (`BUILD_VERSION`: the `git describe` of each Zephyr tree) can
differ between the two trees.

`wake-m4-validate` checks if the hooks measure the mask time of each call
site. It compares the direct values of the site table with a
calibration, with a probe of a known length, and with the IRQ tail of
the same run and of other `ws-up` experiments. The checks H2 c and d
read the current evidence run of `wake-timers-1m` (an import). The
values in the table are from the earlier runs. They were the basis of
the limits:

| Point | Earlier `ws-up` value |
|---|---|
| `cal-t0` | `wake-timers-1m` `t0-default`: IRQ p50 81, ISR to thread p50 1575 cycles. The point gives the cost of the hooks on these two p50 values. |
| `t64-same` | `wake-systick-prio-1m` `t64-same`: IRQ p99.99 5312, max 7775. |
| `t64-lower` | `wake-systick-prio-1m` `t64-lower`: IRQ max 2330. |
| `t256-same` | `wake-systick-prio-1m` `t256-same`: IRQ p99.99 24704, max 34762. |
| `t256-lower` | `wake-systick-prio-1m` `t256-lower`: IRQ p99.99 6592, max 6898. This is the "sharp stop at about 7000" of review-2026-10-25 §4 finding 8. |
| `t256-wheel` | `wake-timeout-backends-1m` `wheel`: IRQ p99.99 5056, max 7160. The WHEEL backend has no DLIST insert walk. |

Each run has the calibration (`m4_floor_cyc`, `m4_pair_cost_cyc`), but
the point `cal-t0` has no load. The point `probe-t0` checks the direct
method (the probe site) and the indirect method (the IRQ tail) against
a known value.

The main cross check is in `t64-lower` and `t256-lower`. With SysTick
one level lower, the IRQ max of the run must be the longest mask
section plus a small rest. If the IRQ max is clearly larger, M4 does
not see a mask path (`m4-design.md` §2).

The board time of `wake-m4-validate` is about 12 min: 7 points x (30 s
build and flash + 200000 x 300 us = 60 s + about 10 s output).

The predictions were written on 2026-10-25 (dates from
`hypotheses.yaml`). H1 has the commit `8a6ba03` (build only, no run in
the results). H2, H3 and H4 came before the run
`m4-validate/20261025T235532Z`.

- H1: with the hooks off, `ws-up` and `ws-up-irqoff` give the same
  image for each point. Only the version strings can differ.
- H2: the cost of the hooks is known and small. The calibration of each
  run measures it, and the hooks add about this cost to the wake path.
- H3: the hooks measure a mask section of a known length. The probe
  site gives the length of the probe, and the IRQ tail of the same run
  shows it.
- H4: the M4 sites contain all mask paths of the IRQ tail. With SysTick
  one level lower, the IRQ max of the run is the longest mask section +
  100..300 cycles.

## References

- `hypotheses.yaml`: the hypotheses H1 to H4, and their checks.
- `ex-wake-m4-image-check/experiment.md`: the build check.
- `ex-wake-m4-validate/experiment.md`: the check of the site values.
- `doc/benchmark-guide/explanation/mask-time.rst`: the M4 method, the hooks, the
  calibration and the probe.
- `st-zephyr-versions/ex-wake-timers-1m/experiment.md`,
  `st-zephyr-versions/ex-wake-systick-prio-1m/experiment.md` and
  `st-zephyr-versions/ex-wake-timeout-backends-1m/experiment.md`:
  the source of the points and the earlier `ws-up` values.
- `st-mask-time/study.md`: the study that uses the instrument.
- `claude/latency-benchmarks/m4-design.md` §2, §3, §4 and §5.1 (outside
  this repository): the mask paths, the cost estimates, the build
  checks and `wake-m4-validate`.
- `claude/latency-benchmarks/review-2026-10-25` §4 finding 8 (outside
  this repository): the sharp stop of the IRQ tail.
