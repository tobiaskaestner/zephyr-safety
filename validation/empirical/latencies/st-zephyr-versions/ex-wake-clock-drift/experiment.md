# wake-clock-drift

## What it measures

App `wake_latency`, `LAT META` keys `clock_drift_cyc` and
`clock_elapsed_cyc`: the cycles that the kernel cycle counter loses
against TIM2, for different numbers of SysTick reprograms.

The study `zephyr-versions` owns this experiment. The study
`measurement-validity/clock-drift` reads it with an import.

## Method

- Tree `ws-up`. Semaphore wake (`LATBENCH_WAKE_SEM`).
- 200000 samples per point.
- The points are the cube `anchor` x `timers` (id `<anchor>-<timers>`).
  They change the number of SysTick reprograms.

## Axes

- **anchor**: `default` is the board defaults with time slicing: each
  wake reprograms SysTick for the slice timeout. `noslice`
  (`TIMESLICING=n`) has no slice timeout, thus fewer reprograms. `switch`
  (`common/conf/use_switch.conf`) is the other arch interface for the
  context switch.
- **timers**: `t0` has no load timers: the slice timeout is often the
  first timeout in the queue. `t16` (`LATBENCH_LOAD_TIMERS=16`): the
  slice timeout is then seldom the first timeout, thus fewer reprograms.
