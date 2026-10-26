# systick-prio-1m

## Question

Does the IRQ tail get smaller when SysTick has a lower priority than the
device IRQ?

In `wake-timers-1m` the SysTick ISR (load timer callbacks and restarts)
makes the IRQ tail: p99.99 5600 cycles at 64 timers, 25600 cycles at 256
timers. The driver gives SysTick the same priority as the stimulus IRQ.
If both are pending, SysTick goes first.

## Method

App `wake_latency`: semaphore given from the wrapped ISR. 1M samples per
point. 2048 fine bins and 2048 coarse bins.

The points are the cube `timers` x `prio` (id `<timers>-<prio>`).

| Point | Settings | Why |
|---|---|---|
| `t64-*`, `t256-*` | `LATBENCH_LOAD_TIMERS` = 64, 256 | Periodic load timers (10..100 ms). These loads gave the IRQ tail in `wake-timers-1m`. |
| `*-same` | driver default | SysTick and EXTI0 at priority 0. |
| `*-lower` | `LATBENCH_SYSTICK_PRIO=1` | SysTick at priority 1. EXTI0 can preempt the SysTick ISR outside its locked sections. |

The locked sections of the SysTick ISR (timeout lock, clock lock) mask
EXTI0 through BASEPRI at all priorities.

## References

- Open item L1 (`later.md`): SysTick priority lower than the device IRQ.
- `../wake-timers-1m/experiment.md`: the IRQ tail with load timers.
