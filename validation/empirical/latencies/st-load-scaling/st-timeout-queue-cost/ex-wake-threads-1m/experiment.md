# wake-threads-1m

## Question

How do the IRQ latency (`irq`, M1) and the ISR to thread wake latency
(`isr2thr`, M2) change with the number and the kind of load threads?
This experiment is the thread axis of the latency plan (§2.4).

## Method

App `wake_latency`: semaphore given from the wrapped ISR, the woken
thread at priority 0. Board defaults (`SCHED_SIMPLE`, time slicing on).
1M samples per point. 2048 fine bins and 2048 coarse bins.

The points are the cube `kind` x `threads` (id `<kind>-<threads>`) and
the point `none-n0`.

| Point | Settings | Why |
|---|---|---|
| `blocked-*` | `LATBENCH_LOAD_THREAD_BLOCKED` | Each load thread waits forever on a semaphore of its own (priority 5). |
| `sleeper-*` | `LATBENCH_LOAD_THREAD_SLEEPER` | Each load thread sleeps 1..20 ms in a loop (priority 5). Each sleep adds a timeout and a thread switch. |
| `busy-*` | `LATBENCH_LOAD_THREAD_BUSY` | Each load thread runs a busy loop at the lowest priority. With time slicing, the busy threads take turns at each slice expiry (20 ms). |
| `*-n2` .. `*-n64` | `LATBENCH_LOAD_THREADS` = 2, 8, 16, 64 | The number of load threads. |
| `none-n0` | no load threads | The reference. It is the same binary as the other points, apart from the load. |

The point `none-n0` has the axis values `kind: none` and `threads: n0`.
These values are not on the cube axes, so `n0` has no number.

## References

- Latency plan §2.4: the load generators.
- `../ex-wake-timers-1m/experiment.md`: the timer axis with the same app.
