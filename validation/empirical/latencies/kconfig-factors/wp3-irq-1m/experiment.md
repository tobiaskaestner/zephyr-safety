# wp3-irq-1m

## Question

How does each WP3 Kconfig factor change the IRQ to ISR latency (`irq`),
against the point `baseline` of the same run?

## Method

App `irq_latency`, wrapped ISR path, idle CPU, hot code in the CCM SRAM.
Random stimulus interval 100..500 us. 1M samples per point.

The axis `variant` changes one Kconfig factor at a time against the
defaults of the app. `../wp3-variants.md` gives the variants, the defaults
and the Kconfig traps. The experiments `wp3-wake-1m` and `wp3-t2t-1m`
have the same variants.

| Point | Settings | Why |
|---|---|---|
| `baseline` .. `no-mpu-guard` | the 11 values of the axis `variant`, no load | Each factor alone, on an idle CPU. |
| `baseline-t64` | `LATBENCH_LOAD_TIMERS=64` | The reference for the other points with 64 load timers. |
| `ticks1000-t64` | `ticks1000` and 64 load timers | 1000 ticks/s puts the expiries of the timers into fewer ticks. |
| `tickless-off-t64` | `tickless-off` and 64 load timers | A SysTick ISR every 100 us, also when no timer expires. |
| `tickless-off-100-t64` | `tickless-off-100` and 64 load timers | A SysTick ISR every 10 ms that handles the expiries of 10 ms. |

The explicit points have the axis `load` (`t64`). The points of the
axis `variant` have the load `none`.

On the IRQ entry path, the kernel does no scheduling and saves no FP
context. Thus the scheduler variants and `fpu-sharing` are references
for "no change".

## References

- `../wp3-variants.md`: the variants and the Kconfig traps.
- `measurement-validity/code-placement`: the hot code in the CCM SRAM.
- `wp3-kconfig-ranking.md` (project notes, not in this repository): the
  ranked list of the Kconfig factors.
