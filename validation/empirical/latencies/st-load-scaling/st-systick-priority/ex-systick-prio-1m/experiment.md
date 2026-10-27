# systick-prio-1m

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`: the IRQ latency and
the ISR to thread wake latency with periodic load timers, with SysTick
at the priority of the device IRQ and at a lower priority.

## Method

- Trees `ws-safety` and `ws-up`. Semaphore given from the wrapped ISR.
- 1M samples per point. 2048 fine bins and 2048 coarse bins.
- The points are the cube `timers` x `prio` (id `<timers>-<prio>`).

## Axes

- **timers**: the number of periodic load timers (10..100 ms),
  `LATBENCH_LOAD_TIMERS` = 64 (`t64`) or 256 (`t256`).
- **prio**: the SysTick priority. `same` is the driver default: SysTick
  and EXTI0 at priority 0. `lower` (`LATBENCH_SYSTICK_PRIO=1`) is
  SysTick at priority 1.
