# irq-baseline-1m

## What it measures

App `irq_latency`, metric `irq`: the IRQ entry latency of the four
interrupt paths, with the board defaults and an idle CPU.
The 1M samples per point are for plots of the distribution and of its
tail.

The study `zephyr-versions` owns this experiment. The study
`default-latencies/irq-entry` reads it with an import.

## Method

- Tree `ws-up`, board defaults, idle CPU.
- 1M samples per point. Random stimulus interval 100..500 us.
- The points are the cube `path` x `background`. Thus the point ids are
  the same as in `irq-smoke`.

## Axes

- **path**: the interrupt path. `stock` is the GPIO driver callback
  (`LATBENCH_IRQ_PATH_STOCK`). `wrapped` is an own ISR through
  `_isr_wrapper`. `direct` is an own direct ISR, and `direct-idle` is the
  reference point of `irq-checks-1m`. `zli` is an own direct
  zero-latency ISR.
- **background**: one value, `idle`. The axis keeps the point ids the
  same as in `irq-smoke`.
