# irq-smoke

## Question

Does the method for the IRQ entry latency work? This experiment is the
first check of the method. It measures the four interrupt paths with the
board defaults and an idle CPU.

The experiment also asks: does the wake-up of the CPU from WFI make the
second mode of the latency?

## Method

App `irq_latency`, tree `ws-safety`, board defaults. The sample count
and the stimulus are the defaults of the app. The points have the axes
`path` and `background` of `irq-baseline-1m`.

| Point | Settings | Why |
|---|---|---|
| `stock-idle` | `LATBENCH_IRQ_PATH_STOCK`, idle CPU | The GPIO driver callback (the default path of the app). |
| `wrapped-idle` | `LATBENCH_IRQ_PATH_WRAPPED`, idle CPU | An own ISR through `_isr_wrapper`. |
| `direct-idle` | `LATBENCH_IRQ_PATH_DIRECT`, idle CPU | An own direct ISR. |
| `zli-idle` | `LATBENCH_IRQ_PATH_ZLI`, idle CPU | An own direct zero-latency ISR. |
| `direct-busy` | `LATBENCH_IRQ_PATH_DIRECT`, `LATBENCH_BG_BUSY` | With a busy CPU, the idle thread does not run and the CPU does not execute WFI. The compare with `direct-idle` shows if the WFI wake-up makes the second mode. |

## References

- `../irq-baseline-1m/experiment.md`: the same four paths with 1M samples.
- `tests/benchmarks/irq_latency/Kconfig`: the paths and the defaults of the app.
