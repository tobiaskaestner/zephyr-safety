# code-generation

## Background

This study measures how the code generation options change the IRQ
entry, the ISR to thread wake and the thread to thread latency. The
question of the study is in `study.yaml`. The study tests these
variants:

- `speed-opt` (`SPEED_OPTIMIZATIONS=y`): the compiler optimizes for
  speed, not for size. The hardware does most of the IRQ entry, so the
  compiler has little code to change there.
- `assert` (`ASSERT=y`): the kernel assertions. `ASSERT` adds checks to
  the kernel code, also in the sections with locked interrupts.
- `assert-spin` (`ASSERT=y`, `SPIN_VALIDATE=y`): the kernel assertions
  and the spinlock checks. `SPIN_VALIDATE` adds a check to each spinlock
  pair.
- `fpu-sharing` (`FPU=y`, `FPU_SHARING=y`): the kernel keeps an FP
  context for each thread. PendSV examines the FP bit of `EXC_RETURN`.
  The IRQ entry path saves no FP context.

## Experiments

This study owns no experiment. It imports `irq-kconfig-1m`, `wake-kconfig-1m`
and `thread-kconfig-1m` from the parent study `kconfig-factors`. The checks
compare each variant with `baseline` of the same run. The checks of
`assert-spin` on the wake paths compare it with `assert`.

The predictions were written on 2026-10-25, before the runs
`wp3-t2t-1m/20261025T203235Z`, `wp3-wake-1m/20261025T205806Z` and
`wp3-irq-1m/20261025T223624Z` (dates from `hypotheses.yaml`):

- H1: `SPEED_OPTIMIZATIONS` makes the kernel paths faster. The
  `isr2thr` and `t2t` p50 decrease by 10..25 %. The `irq` p50 decreases
  by 0..10 cycles only.
- H2: the kernel assertions make the paths slower. `ASSERT` increases
  the `isr2thr` and `t2t` p50 by 5..15 %. `SPIN_VALIDATE` adds
  100..150 cycles more. On the IRQ entry, both increase the p50 by
  0..10 cycles and make the max a little higher.
- H3: `FPU_SHARING` increases the `isr2thr` and `t2t` p50 by
  0..30 cycles, because PendSV examines one bit for the FP context. The
  `irq` p50 does not change (+-2 cycles).

This study has no central result of its own. The rankings of the parent
study give the measured change of each variant.

## References

- `hypotheses.yaml`: the hypotheses H1, H2 and H3, and their checks.
- `../wp3-variants.md`: the variants.
- `../study.md`: the three experiments.
