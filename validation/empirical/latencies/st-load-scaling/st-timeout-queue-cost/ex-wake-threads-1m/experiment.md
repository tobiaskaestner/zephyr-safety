# wake-threads-1m

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`: the IRQ latency (M1)
and the ISR to thread wake latency (M2) with different numbers and kinds
of load threads.

## Method

- Trees `ws-safety` and `ws-up`. Semaphore given from the wrapped ISR,
  the woken thread at priority 0.
- Board defaults (`SCHED_SIMPLE`, time slicing on).
- 1M samples per point. 2048 fine bins and 2048 coarse bins.
- The points are the cube `kind` x `threads` (id `<kind>-<threads>`) and
  the point `none-n0`.

## Axes

- **kind**: the kind of load thread. `blocked`
  (`LATBENCH_LOAD_THREAD_BLOCKED`): each thread waits forever on a
  semaphore of its own (priority 5). `sleeper`
  (`LATBENCH_LOAD_THREAD_SLEEPER`): each thread sleeps 1..20 ms in a
  loop (priority 5). `busy` (`LATBENCH_LOAD_THREAD_BUSY`): each thread
  runs a busy loop at the lowest priority.
- **threads**: the number of load threads (`LATBENCH_LOAD_THREADS`):
  `n2`, `n8`, `n16`, `n64`.
- The point `none-n0` has no load threads, with the axis values
  `kind: none` and `threads: n0`. These values are not on the cube axes,
  so `n0` has no number.
