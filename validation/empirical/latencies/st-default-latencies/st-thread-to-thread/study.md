# thread-to-thread

## Background

This study measures the thread to thread wake latency (M3). The latency
is the time from a wake call in one thread to the first instruction of
the woken thread. All experiments use the app `thread_latency`.

The ISR wakes the giver thread (priority 2) at a random time. The giver
wakes the taker through the kernel object. The metric `t2t` is the time
from the wake call to the taker. By default the taker has priority 1 and
preempts the giver. With `LATBENCH_T2T_PREEMPT: n`, the taker has
priority 3, and no preemption occurs.

The question of the study is in `study.yaml`: how long is the latency
for each kernel object, with the legacy and the new (`USE_SWITCH=y`)
context switch? With the legacy context switch, the thread switch uses
PendSV. With `USE_SWITCH=y`, a thread switch on Cortex-M is
`arch_switch()` inline in `z_swap()`, in thread mode, without PendSV.

The stimulus comes every 50..150 us, not every 100..500 us as in the M2
experiments. This keeps the board time short. All points of the study
use the same stimulus, so they compare with each other. The share of the
samples that meet the timer ISR is about 3 times larger than in the M2
experiments.

## Experiments

The study has no experiments of its own. It reads `thread-baseline-1m`
and `thread-switch` with imports. The study `zephyr-versions` owns the
two experiments.

`thread-baseline-1m` measures M3 for each of the 11 kernel objects, with
the board and kernel defaults. It runs on the tree `ws-up`, with 1M
samples per point. Two more points measure the semaphore and the mutex
without preemption. With two trees, the board time was about 1 h. The
central result `t2t-p99-sem` in `study.yaml` comes from the point `sem`.
This experiment stated no prediction before its run.

`thread-switch` measures M3 with the new arch interface
(`USE_SWITCH=y`), on the tree `ws-up`. It asks: does the wake have the same
two modes as with PendSV? It uses the settings of `thread-baseline-1m`,
for the semaphore and the mutex. Its legacy points are the reference
from the same session. They have the same settings as `sem` and `mutex`
in `thread-baseline-1m`.

The predictions for `thread-switch` were written on 2026-10-25,
before the run `thread2thread-switch/20261025T100427Z` (dates from
`hypotheses.yaml`):

- H1: with `USE_SWITCH=y` the wake has the same two modes as with
  PendSV. About 20 % of the samples have no SysTick reprogram, and about
  80 % have two. The basis: the slice reset is in `update_cache()` and
  does not depend on the arch interface.
- H2: the thread switch costs more with `USE_SWITCH=y` than with PendSV.
  The mean `t2t` is larger, for the semaphore and for the mutex. The
  basis: in `wake-anchors-1m`, `USE_SWITCH=y` adds about 280 cycles per
  ISR wake.

## References

- `hypotheses.yaml`: the hypotheses H1 and H2, and their checks.
- `st-zephyr-versions/ex-thread-baseline-1m/experiment.md`: the legacy
  points of all kernel objects.
- `st-zephyr-versions/ex-thread-switch/experiment.md`: the same
  measurement with `USE_SWITCH=y`.
- `st-zephyr-versions/ex-wake-anchors-1m/experiment.md`:
  the cost of `USE_SWITCH=y` for the ISR wake.
- `update_cache()` in `kernel/sched.c`: the slice reset.
- `tests/benchmarks/thread_latency/Kconfig`: the kernel objects and
  `LATBENCH_T2T_PREEMPT`.
