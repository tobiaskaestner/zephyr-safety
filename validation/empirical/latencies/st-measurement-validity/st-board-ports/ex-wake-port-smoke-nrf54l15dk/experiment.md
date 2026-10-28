# wake-port-smoke-nrf54l15dk

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`: a smoke test of the port
of the benchmark to the board `nrf54l15dk/nrf54l15/cpuapp`. `run.py` must build the image,
flash the board and read the console.

## Method

- Tree `ws-up`, board defaults.
- 10000 samples.

## Axes

- **variant**: one value, `default` (the board defaults). The point
  `default` is the first check of the port.
