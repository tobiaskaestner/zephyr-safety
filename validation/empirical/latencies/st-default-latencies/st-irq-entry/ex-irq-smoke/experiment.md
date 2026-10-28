# irq-smoke

## What it measures

App `irq_latency`, metric `irq`: the IRQ entry latency of the four
interrupt paths, with the board defaults and an idle CPU. It also
measures the direct path with a busy CPU. It is the first check of the
method.

## Method

- Tree `ws-up`, board defaults.
- The sample count and the stimulus are the defaults of the app.
- No cube: five explicit points. The points have the axes `path` and
  `background` of `irq-baseline-1m`.

## Axes

- **path**: the interrupt path. `stock` is the GPIO driver callback
  (`LATBENCH_IRQ_PATH_STOCK`). `wrapped` is an own ISR through
  `_isr_wrapper`. `direct` is an own direct ISR. `zli` is an own direct
  zero-latency ISR.
- **background**: `idle` or `busy` (`LATBENCH_BG_BUSY`, point
  `direct-busy` only). With a busy CPU, the CPU does not execute WFI.
  The compare with `direct-idle` shows the effect of the WFI wake-up.
