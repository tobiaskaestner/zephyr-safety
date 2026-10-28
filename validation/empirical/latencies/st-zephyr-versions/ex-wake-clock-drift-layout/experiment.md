# wake-clock-drift-layout

## What it measures

App `wake_latency`, `LAT META` keys `clock_drift_cyc` and
`clock_elapsed_cyc`: the clock drift of the same wake with two
histogram sizes and two sample counts.

## Method

- Trees `ws-safety` and `ws-up`. Semaphore wake (`LATBENCH_WAKE_SEM`),
  time slicing, no load timers.
- The points are the cube `bins` x `samples` (point id
  `<bins>-<samples>`).

## Axes

- **bins**: `hdefault` is the default bins of the app, the histogram
  size of `wake-clock-drift`. `hcoarse` (2048 fine bins and 2048 coarse
  bins) is the histogram size of `wake-timers-1m`. The histogram size
  changes the code and data layout.
- **samples**: `s200k` (200000 samples) is the sample count of
  `wake-clock-drift`. `s1m` (1000000 samples) is the sample count of
  `wake-timers-1m`.
