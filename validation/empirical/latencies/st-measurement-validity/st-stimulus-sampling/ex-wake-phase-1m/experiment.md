# wake-phase-1m

## What it measures

App `wake_latency`, metric `isr2thr`: the ISR to thread wake latency by
the tick phase of the stimulus edge, with a random and with a fixed
stimulus.

## Method

- Tree `ws-safety`. Semaphore given from the wrapped ISR, board
  defaults.
- 1M samples per point.
- The app records each sample in one of 64 bins by the tick phase of the
  stimulus edge.

## Axes

- **stimulus**: `random` is a random interval of 100..500 us, as in
  `wake-isr-1m`. `fixed-scan` is a fixed period of 300 us + 1 cycle:
  the tick phase moves by 1 cycle per edge.
