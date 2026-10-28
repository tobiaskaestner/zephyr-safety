# thread-m4

## What it measures

App `thread_latency`, metrics `m4.mask` and `m4.isr`: the interrupt
mask sites that a thread to thread wake adds, and their length, for a
semaphore and for a mutex.

## Method

- Tree `ws-up-irqoff` with `CONFIG_ARM_IRQ_MASK_HOOKS` and
  `CONFIG_ARM_IRQ_MASK_HOOKS_ISR`.
- The ISR wakes the giver, and the giver wakes the taker. The taker has
  priority 1 and preempts the giver. Time slicing on, DLIST backend.
- Stimulus interval 50..150 us, as in `thread-baseline-1m`.
- 200000 samples per point. Latency histograms of 1024 fine bins and
  1024 coarse bins of 64 cycles. All values are in cycles at 170 MHz.
- The latency histograms are not data (`LAT META m4=1`). The analysis
  uses the M4 tables (`scripts/benchmarks/m4.py`) only.
- The points are the cube `primitive` x `timers`.

## Axes

- **primitive**: `sem` (`LATBENCH_T2T_SEM`): the sites of the semaphore
  wake in thread context. `mutex` (`LATBENCH_T2T_MUTEX`): the lock and
  unlock sites, with the priority inheritance under the lock.
- **timers**: `t0` has no load timers. `t64` has 64 periodic load
  timers: the timeout walk in the thread app, against `wake-m4-sweep` and
  `wake-m4-validate`.
