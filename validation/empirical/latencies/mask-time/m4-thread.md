# m4-thread

## Question

Which interrupt mask sites does a thread to thread wake add, and how long
are they, for a semaphore and for a mutex?

## Method

App `thread_latency`: the ISR wakes the giver, and the giver wakes the
taker through a semaphore or a mutex. The taker has priority 1 and
preempts the giver. Stimulus interval 50..150 us, as in
`thread2thread-1m`. Time slicing on, DLIST backend. Tree `ws-up-irqoff`
with `CONFIG_ARM_IRQ_MASK_HOOKS` and `CONFIG_ARM_IRQ_MASK_HOOKS_ISR`.
200000 samples per point, latency histograms of 1024 fine bins and 1024
coarse bins of 64 cycles. All values are in cycles at 170 MHz.

The latency histograms of these runs are not data (`LAT META m4=1`). The
analysis uses the M4 tables (`scripts/benchmarks/m4.py`) only.

| Point | Settings | Why |
|---|---|---|
| `sem-t0` | semaphore, no load timers | The sites of the semaphore wake in thread context. |
| `sem-t64` | semaphore, 64 periodic load timers | The timeout walk in the thread app, against `m4-sweep` and `m4-validate`. |
| `mutex-t0` | mutex, no load timers | The lock and unlock sites, with the priority inheritance under the lock. |
| `mutex-t64` | mutex, 64 periodic load timers | As `sem-t64`. |

Board time: 4 points x (30 s + 200000 x 100 us = 20 s + 10 s), about
4 min.

## References

- `doc/benchmark-guide/m4.rst`: the M4 method and the site names.
- `default-latencies/thread-to-thread/thread2thread-1m.md`: the same app
  without hooks.
- `m4-sweep.md` and `measurement-validity/mask-instrumentation/m4-validate.md`:
  the values at 64 timers in `wake_latency`.
- `claude/latency-benchmarks/m4-design.md` §5.3 (outside this repository).
