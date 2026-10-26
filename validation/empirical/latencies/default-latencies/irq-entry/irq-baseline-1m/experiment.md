# irq-baseline-1m

## Question

What is the IRQ entry latency of the four interrupt paths, with the
board defaults and an idle CPU, on both trees? The experiment has 1M
samples per point, for plots of the distribution and of its tail.

## Method

App `irq_latency`, trees `ws-safety` and `ws-up`, board defaults, idle
CPU. 1M samples per point. Random stimulus interval 100..500 us.

The points are the cube `path` x `background`. The axis `background`
has one value, `idle`. Thus the point ids are the same as in `irq-smoke`.

| Point | Settings | Why |
|---|---|---|
| `stock-idle` | `LATBENCH_IRQ_PATH_STOCK` | The GPIO driver callback. |
| `wrapped-idle` | `LATBENCH_IRQ_PATH_WRAPPED` | An own ISR through `_isr_wrapper`. |
| `direct-idle` | `LATBENCH_IRQ_PATH_DIRECT` | An own direct ISR. The reference point of `irq-checks-1m`. |
| `zli-idle` | `LATBENCH_IRQ_PATH_ZLI` | An own direct zero-latency ISR. |

## References

- `../irq-smoke/experiment.md`: the first check of the method.
- `../irq-checks-1m/experiment.md`: the checks of the modes against `direct-idle`.
