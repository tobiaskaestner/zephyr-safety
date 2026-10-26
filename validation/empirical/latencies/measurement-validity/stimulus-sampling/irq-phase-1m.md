# irq-phase-1m

## Question

Does the random stimulus cover the kernel tick evenly? Where in the tick
do the second mode and the tail of the IRQ to ISR latency come from?

## Method

App `irq_latency`, direct ISR path, idle, board defaults, 1M samples per
point. The app records each sample in one of 64 bins by the tick phase of
the stimulus edge.

| Point | Stimulus | Why |
|---|---|---|
| `random` | random interval 100..500 us | The stimulus of all other experiments. Its phase histogram shows the coverage of the tick. |
| `fixed-scan` | fixed period 300 us + 1 cycle | 300 us is 3 ticks, so the tick phase moves by 1 cycle per edge. The scan covers the full tick about 59 times in 1M samples. |

## References

- Same method for the ISR to thread wake: `wake-phase-1m.md`.
