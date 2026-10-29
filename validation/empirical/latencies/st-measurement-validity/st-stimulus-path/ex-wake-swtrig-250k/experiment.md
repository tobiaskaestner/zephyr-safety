# wake-swtrig-250k

## What it measures

App `wake_latency` (semaphore, wrapped ISR) with `LATBENCH_SWTRIG`: each
edge sample is followed by a software sample. The edge meets the idle
thread or a busy thread. The software trigger meets the spinning trigger
thread (priority `LATBENCH_WAKE_PRIO` + 1, preemptible), as in the
scenario `irq_to_thread` of the upstream benchmark. Metrics `isr2thr`,
`irq2thr` and their `_sw` forms. The witness tables (`LATBENCH_TAIL`)
show if SysTick was reprogrammed or interrupted during each tail sample.

## Method

- Tree `ws-up`, 250000 samples per point (each with an edge and a
  software sample), random stimulus interval 100..500 us.
- Code in flash. With the software trigger the app has six histograms,
  and it does not fit into the RAM that `LATBENCH_CODE_RAM` leaves. The
  edge and the software samples of one point come from one image, so
  their difference is free of the code placement effect. A difference
  across points can contain up to about 30 cycles of it.
- The p50 of `isr2thr` is in the slow mode (about 80 % of the samples),
  the p10 in the fast mode (about 20 %), see `st-isr-to-thread`.

## Axes

- **config**: `default` (time slicing and stack guard on), `noslice`
  (`TIMESLICING=n`) and `pr-config` (no slicing, no stack guard: the
  `prj.conf` of the upstream benchmark).
- **background**: `idle` or `busy` (`LATBENCH_BG_BUSY`: a busy thread at
  the lowest priority, preemptible and sliced). The edge from the busy
  thread tests the cost of a preempted thread without the trigger
  thread.
