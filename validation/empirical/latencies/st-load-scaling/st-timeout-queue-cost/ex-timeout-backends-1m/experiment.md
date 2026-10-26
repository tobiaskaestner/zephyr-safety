# timeout-backends-1m

## Question

How does the timeout queue backend change the IRQ latency (`irq`, M1)
and the ISR to thread wake latency (`isr2thr`, M2) with 256 periodic
load timers?

## Method

App `wake_latency`: semaphore given from the wrapped ISR. 256 periodic
load timers (`LATBENCH_LOAD_TIMERS=256`). 1M samples per point. 2048
fine bins and 2048 coarse bins.

| Point | Settings | Why |
|---|---|---|
| `dlist` | `TIMEOUT_BACKEND_DLIST` | The default backend. It gives a reference in the same binary as the other points. |
| `minheap` | `TIMEOUT_BACKEND_MINHEAP`, `TIMEOUT_HEAP_MAX_ENTRIES=320` | A backend under test. |
| `wheel` | `TIMEOUT_BACKEND_WHEEL` | A backend under test. |
| `bucket` | `TIMEOUT_BACKEND_BUCKET` | A backend under test. |

The SKIPLIST backend is only in the tree `ws-up`. It is in
`timeout-skiplist-1m`.

## References

- `../ex-timeout-skiplist-1m/experiment.md`: the SKIPLIST backend.
- `../ex-wake-timers-1m/experiment.md`: the point `t256-default` has the same load with
  the DLIST backend.
