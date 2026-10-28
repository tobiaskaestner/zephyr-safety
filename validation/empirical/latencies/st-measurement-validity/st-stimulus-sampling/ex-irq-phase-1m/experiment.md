# irq-phase-1m

## What it measures

App `irq_latency`, metric `irq`: the IRQ to ISR latency by the tick
phase of the stimulus edge, with a random and with a fixed stimulus.

## Method

- Tree `ws-up`. Direct ISR path, idle CPU, board defaults.
- 1M samples per point.
- The app records each sample in one of 64 bins by the tick phase of the
  stimulus edge.

## Axes

- **stimulus**: `random` is a random interval of 100..500 us, the
  stimulus of all other experiments. Its phase histogram shows the
  coverage of the tick. `fixed-scan` is a fixed period of 300 us +
  1 cycle: the tick phase moves by 1 cycle per edge.
