# wp3-irq-1m

## What it measures

App `irq_latency`, metric `irq`: the IRQ entry latency for each WP3
Kconfig factor, against the point `baseline` of the same run.

## Method

- Tree `ws-up`. Wrapped ISR path, idle CPU, hot code in the CCM SRAM.
- Random stimulus interval 100..500 us. 1M samples per point.
- The points are the 11 values of the axis `variant` with no load, plus
  four explicit points with 64 load timers.

## Axes

- **variant**: one Kconfig factor at a time against the defaults of the
  app. `../wp3-variants.md` gives the variants, the defaults and the
  Kconfig traps. `wp3-wake-1m` and `wp3-t2t-1m` have the same variants.
- **load**: `none` for the points of the axis `variant`. `t64`
  (`LATBENCH_LOAD_TIMERS=64`) for the explicit points `baseline-t64`,
  `ticks1000-t64`, `tickless-off-t64` and `tickless-off-100-t64`.
  `baseline-t64` is the reference of the other `t64` points.
