# stack-guard

## Background

This study measures how much the MPU stack guard adds to the IRQ entry,
the ISR to thread wake and the thread to thread latency. The question of
the study is in `study.yaml`.

The defaults of the apps have `MPU_STACK_GUARD=y`. PendSV updates the
MPU region of the stack guard at each thread switch. Each wake and each
`t2t` sample has one thread switch. The IRQ entry path has no scheduler
and no FP context.

The variant `no-mpu-guard` sets `HW_STACK_PROTECTION=n` and
`MPU_STACK_GUARD=n`. `MPU_STACK_GUARD=n` alone has no effect.
`../wp3-variants.md` gives this Kconfig trap.

## Experiments

This study owns no experiment. It imports `irq-kconfig-1m`, `wake-kconfig-1m`
and `thread-kconfig-1m` from the parent study `kconfig-factors`. The checks
compare `no-mpu-guard` with `baseline` in all three experiments.

The prediction was written on 2026-10-25, before the runs
`wp3-t2t-1m/20261025T203235Z`, `wp3-wake-1m/20261025T205806Z` and
`wp3-irq-1m/20261025T223624Z` (dates from `hypotheses.yaml`):

- H1: without the MPU stack guard, PendSV skips the update of the MPU
  region. Thus the `isr2thr` and `t2t` p50 decrease by 100..250 cycles.
  The IRQ entry has no thread switch. Thus the `irq` p50 does not change
  (+-2 cycles).

This study has no central result of its own. The rankings of the parent
study give the measured change of each variant.

## References

- `hypotheses.yaml`: the hypothesis H1 and its checks.
- `../wp3-variants.md`: the variants and the Kconfig trap of
  `no-mpu-guard`.
- `../study.md`: the three experiments.
