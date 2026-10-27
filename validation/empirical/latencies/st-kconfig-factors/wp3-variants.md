# WP3 variants

The experiments `wp3-irq-1m`, `wp3-wake-1m` and `wp3-t2t-1m` have the
same axis `variant`. This file describes the variants one time for the
three experiments.

## Defaults of the apps

Each variant changes one Kconfig factor against the defaults of the
apps:

- `SIZE_OPTIMIZATIONS`
- `SCHED_SIMPLE`
- tickless kernel (`TICKLESS_KERNEL=y`), 10000 ticks/s
- time slicing, 20 ms slices
- `MPU_STACK_GUARD=y`
- `ASSERT=n`

The point `baseline` has these defaults. Each check of a hypothesis
compares a variant with the point `baseline` of the same run. The
hypotheses are in the sub-studies `st-kconfig-factors/st-scheduler`,
`st-kconfig-factors/st-tick-mode`, `st-kconfig-factors/st-code-generation` and
`st-kconfig-factors/st-stack-guard`.

## Variants

| Variant | Kconfig | Factor |
|---|---|---|
| `baseline` | (none) | The defaults of the apps. |
| `scalable` | `SCHED_SCALABLE=y` | Run queue as a red-black tree, not as a list. |
| `multiq` | `SCHED_MULTIQ=y` | Run queue as one list for each priority. |
| `ticks1000` | `SYS_CLOCK_TICKS_PER_SEC=1000` | 1000 ticks/s. The kernel stays tickless. |
| `tickless-off` | `TICKLESS_KERNEL=n`, `SYS_CLOCK_TICKS_PER_SEC=10000` | A periodic tick at the tick rate of the baseline. |
| `tickless-off-100` | `TICKLESS_KERNEL=n`, `SYS_CLOCK_TICKS_PER_SEC=100` | The Zephyr default without the tickless kernel. |
| `fpu-sharing` | `FPU=y`, `FPU_SHARING=y` | The kernel keeps an FP context for each thread. |
| `speed-opt` | `SPEED_OPTIMIZATIONS=y` | The compiler optimizes for speed, not for size. |
| `assert` | `ASSERT=y` | Kernel assertions. |
| `assert-spin` | `ASSERT=y`, `SPIN_VALIDATE=y` | Kernel assertions and the spinlock checks. |
| `no-mpu-guard` | `HW_STACK_PROTECTION=n`, `MPU_STACK_GUARD=n` | No MPU stack guard. |

The SysTick runs at 170 MHz. Thus:

- `tickless-off` gives a SysTick ISR every 17000 cycles (100 us).
- `tickless-off-100` gives a SysTick ISR every 1.7M cycles (10 ms).
- `ticks1000` rounds each timeout up to a 1 ms tick (170000 cycles).

## Kconfig traps

The Kconfig of these variants has two traps. The ws-up tree of
`validation/trees.yaml` gives the line numbers.

`tickless-off` sets `SYS_CLOCK_TICKS_PER_SEC=10000` explicitly. Without
`TICKLESS_KERNEL`, the default is 100 ticks/s (`kernel/Kconfig:731`).
Without the explicit value, the variant changes a second factor.

`no-mpu-guard` also sets `HW_STACK_PROTECTION=n`. The board defconfig
sets `HW_STACK_PROTECTION=y`. Then `ARM_STACK_PROTECTION` selects
`MPU_STACK_GUARD` (`arch/arm/core/Kconfig:244-246`), and
`MPU_STACK_GUARD=n` alone has no effect. On this board, the stack guard
is the only effect of `HW_STACK_PROTECTION`. Thus the factor stays the
same.

## References

- `wp3-kconfig-ranking.md` (project notes, not in this repository): the
  ranked list of the Kconfig factors, the source of the variants.
