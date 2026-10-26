# clock-drift

## Question

How many cycles does the kernel cycle counter lose against TIM2, and does
the loss change with the number of SysTick reprograms? TIM2 is the
stimulus timer. It runs on the same clock as the kernel cycle counter.

A first check (unpinned) showed about 8 lost cycles for each SysTick
reprogram. With time slicing, each wake reprograms SysTick for the slice
timeout, unless an earlier timeout is in the queue.

## Method

App `wake_latency`, semaphore wake (`LATBENCH_WAKE_SEM`), 200000 samples
per point, trees ws-safety and ws-up. The app prints the drift in the
`LAT META` keys `clock_drift_cyc` and `clock_elapsed_cyc`.

The points are the cube of the axes `anchor` and `timers`. They change
the number of SysTick reprograms. A point id is `<anchor>-<timers>`.

| Point | Settings | Why |
|---|---|---|
| `default-*` | board defaults, time slicing | Each wake reprograms SysTick for the slice timeout. |
| `noslice-*` | `TIMESLICING=n` | No slice timeout, thus fewer reprograms. |
| `switch-*` | `common/conf/use_switch.conf` | The other arch interface for the context switch. |
| `*-t0` | no load timers | The slice timeout is often the first timeout in the queue. |
| `*-t16` | `LATBENCH_LOAD_TIMERS=16` | The slice timeout is then seldom the first timeout, thus fewer reprograms. |

## References

- The test of the cause: `clock-drift-fix.md`.
