# wake-anchors-1m

## What it measures

App `wake_latency`, metric `isr2thr`: the ISR to thread wake latency
(M2) of the semaphore, given from the wrapped ISR. The points find the
setting that makes the two modes.

The study `zephyr-versions` owns this experiment. No other study
imports it.

## Method

- Tree `ws-up`. 1M samples per point.
- One kernel object is sufficient, because all five objects have the
  same two modes.
- The points are the cube `anchor` x `arch`.

## Axes

- **anchor**: `default` is the board and kernel defaults, the
  reference. `noslice` sets only time slicing off (`TIMESLICING: n`).
  `lean` is `common/conf/lean.conf`: no time slicing, no stack guard,
  `-O2`.
- **arch**: `legacy` is the thread switch through PendSV. `switch` is the
  new arch interface (`common/conf/use_switch.conf`).
