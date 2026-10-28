# wake-fast-mode

## What it measures

App `wake_latency`, metric `isr2thr`: the share of the fast mode of the
ISR to thread wake. The points check if the fast mode depends on the
stimulus delay or on other state.

## Method

- Tree `ws-safety`. Semaphore given from the wrapped ISR. 200000 samples
  per point.
- No cube: each point changes one factor against `r100-500` (the app
  defaults).

## Axes

- **stimulus**: the stimulus interval. `r100-500` is a random interval
  of 100..500 us, the default range and the baseline. `r100-200` and
  `r400-500` are different ranges. `fixed300` is a fixed period of
  300 us, plus 1 cycle per edge: a fixed delay.
- **poll**: the poll interval of the main thread, `100ms` (the default)
  or `1000ms` (point `poll1000`). The axis changes other state in the
  main thread.
