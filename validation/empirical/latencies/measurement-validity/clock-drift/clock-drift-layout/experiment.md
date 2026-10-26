# clock-drift-layout

## Question

Why does the same wake (semaphore, time slicing, no load timers) lose 8.0
cycles per wake in `clock-drift`, but 9.7 cycles per wake in
`wake-timers-1m` (point `t0-default`)?

The safety revision of the two runs has the same SysTick code. The two
runs have a different histogram size, and thus a different code and data
layout. They also have a different number of samples.

## Method

App `wake_latency`, semaphore wake (`LATBENCH_WAKE_SEM`), time slicing,
no load timers, trees ws-safety and ws-up. The app prints the drift in
the `LAT META` keys `clock_drift_cyc` and `clock_elapsed_cyc`.

The points are the cube of the axes `bins` and `samples` (point id
`<bins>-<samples>`).

| Point | Settings | Why |
|---|---|---|
| `hdefault-*` | the default bins of the app | The histogram size of `clock-drift`. |
| `hcoarse-*` | 2048 fine bins and 2048 coarse bins | The histogram size of `wake-timers-1m`. |
| `*-s200k` | 200000 samples | The sample count of `clock-drift`. |
| `*-s1m` | 1000000 samples | The sample count of `wake-timers-1m`. |

## References

- `../clock-drift/experiment.md`.
- `wake-timers-1m`: owned by `load-scaling`.
