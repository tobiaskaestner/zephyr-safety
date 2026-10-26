# m4-sweep

## Question

How do the interrupt mask time and the ISR body time of each call site
change with the load timers, the sleeper threads and time slicing?

## Method

App `wake_latency`: semaphore given from the wrapped ISR, idle
background, DLIST backend, SysTick at the driver priority. Tree
`ws-up-irqoff` with `CONFIG_ARM_IRQ_MASK_HOOKS` and
`CONFIG_ARM_IRQ_MASK_HOOKS_ISR`. 200000 samples per point, latency
histograms of 1024 fine bins and 1024 coarse bins of 64 cycles. All
values are in cycles at 170 MHz.

The latency histograms of these runs are not data (`LAT META m4=1`). The
analysis uses the M4 tables (`scripts/benchmarks/m4.py`) only.

The three axes give 24 points. The point id is `<timers>-<sleepers>-<slice>`.

| Point | Settings | Why |
|---|---|---|
| `t0-*`, `t16-*`, `t64-*`, `t256-*` | 0, 16, 64 or 256 periodic `k_timer`s (10..100 ms, random start) | More timeouts in the queue. Each timer restart walks the queue. |
| `*-s0-*`, `*-s8-*`, `*-s64-*` | 0, 8 or 64 sleeper threads (1..20 ms sleeps, priority 5) | More timeouts in the queue. The sleeper wakes run in the SysTick ISR. |
| `*-slice`, `*-noslice` | `TIMESLICING=y` (default, 20 ms) or `TIMESLICING=n` | The slice reset adds a timeout in the EXTI0 ISR and at a switch. |

The "walk" is the DLIST insert walk: about 25 cycles for each timeout that
expires before the new one, with the timeout lock held.

`z_add_timeout()` is one site: its lock is inlined there, so all callers
share it. The context splits the callers:

- SysTick (`e15`): the timer restarts and the sleeper wakes.
- irq6, the EXTI0 ISR (`e22`): the slice reset in the give.
- thread (`t`): the slice reset at a switch, and `k_sleep()`.

Board time: 24 points x (30 s + 200000 x 300 us = 60 s + 10 s), about
40 min.

## References

- `doc/benchmark-guide/m4.rst`: the M4 method and the site names.
- `measurement-validity/mask-instrumentation/m4-validate/experiment.md`: the check of
  the method, and the points `t64-same` and `t256-same`.
- `load-scaling/timeout-queue-cost/wake-timers-1m/experiment.md`: the `ws-up`
  IRQ max at 256 timers.
- `claude/latency-benchmarks/m4-design.md` §5.2 (outside this repository).
