# wake-port-smoke-mimxrt1060_evk

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`: a smoke test of the port
of the benchmark to the board `mimxrt1060_evk@C/mimxrt1062/qspi`.
`run.py` must build the image, flash the board and read the console.

## Method

- Trees `ws-safety` and `ws-up`, board defaults.
- 10000 samples.
- The loopback wire is D2 - A3 (A3 drives, D2 reads).

## Axes

- **variant**: one value, `default` (the board defaults). The point
  `default` is the first check of the port.
