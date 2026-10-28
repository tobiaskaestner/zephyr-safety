# clock-drift

## Background

This study examines the clock drift of the kernel cycle counter. The
counter loses cycles against TIM2, the stimulus timer. TIM2 runs on the
same clock as the kernel cycle counter. The question of the study is in
`study.yaml`: why does the counter lose cycles, and does the loss change
the latency data?

The app `wake_latency` prints the drift in the `LAT META` keys
`clock_drift_cyc` and `clock_elapsed_cyc`. All experiments use the
semaphore wake (`LATBENCH_WAKE_SEM`).

The study tests two causes:

1. The SysTick reprogram. A first check (unpinned) showed about 8 lost
   cycles for each SysTick reprogram. With time slicing, each wake
   reprograms SysTick for the slice timeout, unless an earlier timeout
   is in the queue. With 16 load timers, the slice timeout is seldom the
   first timeout, thus fewer reprograms occur.
2. The loss of whole reloads. The driver programs a reload of 10 us or
   more (`min_delay`), and it sees one counter wrap or less. With 256
   periodic timers, the kernel masks the SysTick IRQ for longer than
   that, because each timeout insert walks the list under the lock.
   Thus the driver can lose whole reloads. An unpinned check gave a
   drift of 4668 ppm.

The tree `ws-safety-driftfix` adds the option
`CORTEX_M_SYSTICK_RELOAD_GAP_COMP` to the SysTick driver. With this
option, the driver measures the uncounted cycles of each reprogram with
the DWT cycle counter. It then adds them to the software count.

## Experiments

`wake-clock-drift` measures how many cycles the counter loses, and if the
loss changes with the number of SysTick reprograms. Its anchors and its
load timers change the number of reprograms. It runs on two trees,
`ws-safety` and `ws-up`.

`wake-clock-drift-fix` tests both causes. It compares the tree with the
option against the same tree without it, for the anchors of
`wake-clock-drift`. Three more points with 256 load timers test the second
cause at three values of the shortest SysTick reload.

`wake-clock-drift-layout` asks a later question. The same wake (semaphore,
time slicing, no load timers) loses 8.0 cycles per wake in
`wake-clock-drift`, but 9.7 cycles per wake in `wake-timers-1m` (point
`t0-default`). The safety revision of the two runs has the same SysTick
code. The two runs have a different histogram size, and thus a
different code and data layout. They also have a different number of
samples. The experiment changes these two factors.

The predictions were written before the runs (dates from
`hypotheses.yaml`):

- H1: each SysTick reprogram loses about 8 cycles. Thus the drift
  changes with the number of reprograms per wake (written 2026-10-24,
  before `clock-drift/20261024T210905Z`). The gap compensation removes
  it (written 2026-10-25, before `clock-drift-fix/20261024T223910Z`).
- H2: with 256 periodic timers, the driver loses whole reloads. A
  longer shortest reload removes this loss (written 2026-10-25, before
  `clock-drift-fix/20261024T223910Z`).

The dates of the predictions for `wake-clock-drift-fix` are local time
(+0200). The run id is UTC: the run started at 00:39 +0200.

`wake-clock-drift-layout` stated no prediction before its run. Its drift
values are the central result `layout-drift`. A person confirms the
central result `drift-cause` from H1 and H2.

## References

- `hypotheses.yaml`: the hypotheses H1 and H2, and their checks.
- `ex-clock-drift/experiment.md`: the first cause and the anchors.
- `ex-clock-drift-fix/experiment.md`: the test of both causes.
- `ex-clock-drift-layout/experiment.md`: the histogram size and the
  sample count.
- `st-load-scaling/st-timeout-queue-cost/ex-wake-timers-1m/experiment.md`:
  the point `t0-default` with 9.7 cycles per wake.
- `tests/benchmarks/common/boards/nucleo_g474re/systick/`: the overlays
  of the shortest reload.
