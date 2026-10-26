# m4-validate

## Question

Do the M4 hooks measure the interrupt mask time of each call site?

The run compares the direct values of the site table with a calibration,
with a probe of a known length, and with the IRQ tail of the same run and
of earlier `ws-up` runs.

## Method

App `wake_latency`: semaphore given from the wrapped ISR, idle
background, time slicing on, DLIST backend. Tree `ws-up-irqoff` with
`CONFIG_ARM_IRQ_MASK_HOOKS` and `CONFIG_ARM_IRQ_MASK_HOOKS_ISR`. 200000
samples per point. All values are in cycles at 170 MHz.

The latency histograms are smaller than in the 1M runs: 1024 fine bins
and 1024 coarse bins of 64 cycles, 0..66559 cycles. The site table needs
the RAM (64 sites x 488 bytes).

The latency histograms of these runs are not data. The hooks make each
mask section longer, and they add time to the wake path. Each log says so
(`LAT META m4=1`, `m4_note`). The analysis uses the M4 tables
(`scripts/benchmarks/m4.py`) only. The IRQ tail of the same run is only a
cross check.

| Point | Settings | Why |
|---|---|---|
| `cal-t0` | no load | The calibration (`m4_floor_cyc`, `m4_pair_cost_cyc`). Each run has it, but this point has no load. The cost of the hooks on the IRQ p50 and the ISR to thread p50, against `ws-up` `wake-timers-1m` `t0-default` (81 and 1575 cycles). |
| `probe-t0` | as `cal-t0`, plus a probe thread that masks for exactly 5000 DWT cycles every 10 ms | A known mask length. It checks the direct method (the probe site) and the indirect method (the IRQ tail) against a known value. |
| `t64-same` | 64 periodic load timers, SysTick at the driver priority | `ws-up` `systick-prio-1m` `t64-same`: IRQ p99.99 5312, max 7775. |
| `t64-lower` | as `t64-same`, SysTick one level lower | `ws-up` `t64-lower`: IRQ max 2330. |
| `t256-same` | 256 periodic load timers, SysTick at the driver priority | `ws-up` `t256-same`: IRQ p99.99 24704, max 34762. |
| `t256-lower` | as `t256-same`, SysTick one level lower | `ws-up` `t256-lower`: IRQ p99.99 6592, max 6898. This is the "sharp stop at about 7000" of review-2026-10-25 §4 finding 8. |
| `t256-wheel` | 256 periodic load timers, WHEEL backend, SysTick at the driver priority | No DLIST insert walk. `ws-up` `timeout-backends-1m` `wheel`: IRQ p99.99 5056, max 7160. |

The main cross check is in `t64-lower` and `t256-lower`. With SysTick one
level lower, the IRQ max of the run must be the longest mask section plus
a small rest. If the IRQ max is clearly larger, M4 does not see a mask
path (`m4-design.md` §2).

Board time: 7 points x (30 s build and flash + 200000 x 300 us = 60 s +
about 10 s output), about 12 min.

## References

- `doc/benchmark-guide/m4.rst`: the M4 method, the calibration and the
  probe.
- `load-scaling/wake-timers-1m/experiment.md`, `load-scaling/systick-prio-1m/experiment.md`,
  `load-scaling/timeout-backends-1m/experiment.md`: the `ws-up` values above.
- `claude/latency-benchmarks/m4-design.md` §2, §3 and §5.1 (outside this
  repository): the mask paths, the cost estimates and this experiment.
- `claude/latency-benchmarks/review-2026-10-25` §4 finding 8 (outside this
  repository): the sharp stop of the IRQ tail.
