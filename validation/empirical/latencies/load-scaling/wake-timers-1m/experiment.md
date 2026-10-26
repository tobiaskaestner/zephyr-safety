# wake-timers-1m

## Question

How do the IRQ latency (`irq`, M1) and the ISR to thread wake latency
(`isr2thr`, M2) change with the number of kernel timers, with and
without time slicing? This experiment is the timer axis of the latency
plan (§2.4).

## Method

App `wake_latency`: semaphore given from the wrapped ISR. Board defaults
(timeout queue backend DLIST). 1M samples per point. 2048 fine bins and
2048 coarse bins of 32 cycles: the histogram covers 0..67583 cycles.

The points are the cube `timers` x `anchor` (id `<timers>-<anchor>`).

| Point | Settings | Why |
|---|---|---|
| `t0-*` | no load timers | The reference. |
| `t16-*`, `t64-*`, `t256-*` | `LATBENCH_LOAD_TIMERS` = 16, 64, 256 | N periodic `k_timer`s, period 10..100 ms, random start. Their expiry functions run in the SysTick ISR. Each restart inserts a timeout into the timeout queue. |
| `t256far-*` | `LATBENCH_LOAD_TIMERS` = 256, `LATBENCH_LOAD_TIMER_FAR` | 256 one-shot timers one hour away. They change only the length of the timeout queue. |
| `*-default` | board default (time slicing on) | Each wake resets the time slice, and the reset inserts a timeout. |
| `*-noslice` | `TIMESLICING=n` | No slice reset in the wake. |

The SysTick ISR and the EXTI0 ISR (the stimulus) have the same priority.

## References

- Latency plan §2.4: the load generators.
- `../wake-threads-1m/experiment.md`: the thread axis with the same app.
- `../systick-prio-1m/experiment.md`: SysTick at a lower priority.
