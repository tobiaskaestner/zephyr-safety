# wake-m4-sweep

## What it measures

App `wake_latency`, metrics `m4.mask` and `m4.isr`: the interrupt mask
time and the ISR body time of each call site, over the load timers, the
sleeper threads and time slicing.

## Method

- Tree `ws-up-irqoff` with `CONFIG_ARM_IRQ_MASK_HOOKS` and
  `CONFIG_ARM_IRQ_MASK_HOOKS_ISR`.
- Semaphore given from the wrapped ISR, idle background, DLIST backend,
  SysTick at the driver priority.
- 200000 samples per point. Latency histograms of 1024 fine bins and
  1024 coarse bins of 64 cycles. All values are in cycles at 170 MHz.
- The latency histograms are not data (`LAT META m4=1`). The analysis
  uses the M4 tables (`scripts/probatrix/benchmarks/m4.py`) only.
- The three axes give 24 points. The point id is
  `<timers>-<sleepers>-<slice>`.

## Axes

- **timers**: 0, 16, 64 or 256 periodic `k_timer`s (10..100 ms, random
  start). More timeouts in the queue. Each timer restart walks the
  queue.
- **sleepers**: 0, 8 or 64 sleeper threads (1..20 ms sleeps,
  priority 5). More timeouts in the queue. The sleeper wakes run in the
  SysTick ISR.
- **slice**: `slice` (`TIMESLICING=y`, the default, 20 ms) or `noslice`
  (`TIMESLICING=n`). The slice reset adds a timeout in the EXTI0 ISR
  and at a switch.
