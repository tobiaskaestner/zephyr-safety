# timeout-backends-1m

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`: the IRQ latency (M1)
and the ISR to thread wake latency (M2) for each timeout queue backend,
with 256 periodic load timers.

## Method

- Trees `ws-safety` and `ws-up`. Semaphore given from the wrapped ISR.
- 256 periodic load timers (`LATBENCH_LOAD_TIMERS=256`).
- 1M samples per point. 2048 fine bins and 2048 coarse bins.

## Axes

- **backend**: the timeout queue backend. `dlist`
  (`TIMEOUT_BACKEND_DLIST`) is the default backend, the reference in the
  same binary. `minheap` (`TIMEOUT_BACKEND_MINHEAP`,
  `TIMEOUT_HEAP_MAX_ENTRIES=320`), `wheel` (`TIMEOUT_BACKEND_WHEEL`) and
  `bucket` (`TIMEOUT_BACKEND_BUCKET`) are the backends under test.
