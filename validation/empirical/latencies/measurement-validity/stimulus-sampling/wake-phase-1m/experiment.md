# wake-phase-1m

## Question

Does the tick phase of the stimulus edge decide between the two modes of
the ISR to thread wake latency (`isr2thr`)? `wake-isr-1m` showed two
modes, 80 % and 20 % of the samples, 310 cycles apart.

## Method

App `wake_latency`, semaphore given from the wrapped ISR, board
defaults, 1M samples per point. The app records each sample in one of 64
bins by the tick phase of the stimulus edge.

| Point | Stimulus | Why |
|---|---|---|
| `random` | random interval 100..500 us | As in `wake-isr-1m`. |
| `fixed-scan` | fixed period 300 us + 1 cycle | 300 us is 3 ticks, so the tick phase moves by 1 cycle per edge. The scan covers the full tick about 59 times in 1M samples. |

## References

- `default-latencies/isr-to-thread/wake-isr-1m/experiment.md`: the two modes.
