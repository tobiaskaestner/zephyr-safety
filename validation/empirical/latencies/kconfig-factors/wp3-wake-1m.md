# wp3-wake-1m

## Question

How does each WP3 Kconfig factor change the ISR to thread wake latency
(`isr2thr`), against the point `baseline` of the same run?

## Method

App `wake_latency`, semaphore given from the wrapped ISR, hot code in the
CCM SRAM. 1M samples per point, 2048 fine and 2048 coarse histogram bins.

The axis `variant` changes one Kconfig factor at a time against the
defaults of the app. `wp3-variants.md` gives the variants, the defaults
and the Kconfig traps. The experiments `wp3-irq-1m` and `wp3-t2t-1m`
have the same variants.

| Point | Settings | Why |
|---|---|---|
| `baseline` .. `no-mpu-guard` | the 11 values of the axis `variant`, no load | Each factor alone, with no load. |
| `baseline-busy16` | `LATBENCH_LOAD_THREAD_BUSY=y`, `LATBENCH_LOAD_THREADS=16` | The reference for the other points with 16 busy threads. |
| `scalable-busy16` | `scalable` and 16 busy threads | Does the cost of the red-black tree grow with the number of threads? |
| `multiq-busy16` | `multiq` and 16 busy threads | The same for one list for each priority. |
| `baseline-t64` | `LATBENCH_LOAD_TIMERS=64` | The reference for the other points with 64 load timers. |
| `ticks1000-t64` | `ticks1000` and 64 load timers | The slice walk over the timeouts at 1000 ticks/s. |
| `tickless-off-t64` | `tickless-off` and 64 load timers | The slice walk without the SysTick reprograms. |
| `tickless-off-100-t64` | `tickless-off-100` and 64 load timers | The same at 100 ticks/s. |

The explicit points have the axis `load` (`busy16` or `t64`). The points
of the axis `variant` have the load `none`.

The busy threads have priority 5. This priority is lower than the
priority of the woken thread.

Without `TICKLESS_KERNEL`, `sys_clock_set_timeout()` returns at once
(ws-up `drivers/timer/system_timer_generic.h:650`). Thus the slice reset
never reprograms the SysTick in `tickless-off` and `tickless-off-100`.

## References

- `wp3-variants.md`: the variants and the Kconfig traps.
- `measurement-validity/code-placement`: the hot code in the CCM SRAM.
- Review of 2026-10-25, §5 (project notes, not in this repository): the
  cost of a sliced busy thread for each wake, from `wake-threads-1m`.
- `load-scaling/wake-threads-1m.md`: the wake with 2..64 busy threads.
- `wp3-kconfig-ranking.md` (project notes, not in this repository): the
  ranked list of the Kconfig factors.
