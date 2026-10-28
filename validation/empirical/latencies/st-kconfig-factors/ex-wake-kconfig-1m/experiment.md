# wake-kconfig-1m

## What it measures

App `wake_latency`, metric `isr2thr`: the ISR to thread wake latency for
each WP3 Kconfig factor, against the point `baseline` of the same run.

## Method

- Tree `ws-up`. Semaphore given from the wrapped ISR, hot code in the
  CCM SRAM.
- 1M samples per point, 2048 fine and 2048 coarse histogram bins.
- The points are the 11 values of the axis `variant` with no load, plus
  seven explicit points with a load.
- The busy threads have priority 5. This priority is lower than the
  priority of the woken thread.

## Axes

- **variant**: one Kconfig factor at a time against the defaults of the
  app. `../wp3-variants.md` gives the variants, the defaults and the
  Kconfig traps. `irq-kconfig-1m` and `thread-kconfig-1m` have the same variants.
- **load**: `none` for the points of the axis `variant`. `busy16`
  (`LATBENCH_LOAD_THREAD_BUSY=y`, `LATBENCH_LOAD_THREADS=16`) for the
  points `baseline-busy16`, `scalable-busy16` and `multiq-busy16`. `t64`
  (`LATBENCH_LOAD_TIMERS=64`) for the points `baseline-t64`,
  `ticks1000-t64`, `tickless-off-t64` and `tickless-off-100-t64`. The
  `baseline` point of each load is the reference of the other points
  with this load.
