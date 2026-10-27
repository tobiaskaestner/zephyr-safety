# wake-timers-1m

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`: the IRQ latency (M1)
and the ISR to thread wake latency (M2) with different numbers of kernel
timers, with and without time slicing.

## Method

- Trees `ws-safety` and `ws-up`. Semaphore given from the wrapped ISR.
- Board defaults (timeout queue backend DLIST).
- 1M samples per point. 2048 fine bins and 2048 coarse bins of
  32 cycles: the histogram covers 0..67583 cycles.
- The points are the cube `timers` x `anchor` (id `<timers>-<anchor>`).

## Axes

- **timers**: the load timers (`LATBENCH_LOAD_TIMERS`). `t0` has no
  load timers, the reference. `t16`, `t64` and `t256` have 16, 64 and
  256 periodic `k_timer`s, period 10..100 ms, random start. `t256far`
  (`LATBENCH_LOAD_TIMER_FAR`) has 256 one-shot timers one hour away.
- **anchor**: `default` is the board default (time slicing on): each
  wake resets the time slice. `noslice` (`TIMESLICING=n`) has no slice
  reset in the wake.
