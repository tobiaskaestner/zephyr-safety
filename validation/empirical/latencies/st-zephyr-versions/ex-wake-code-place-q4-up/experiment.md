# wake-code-place-q4-up

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`, and the clock drift:
the points of `wake-code-place-q4` that the tree comparison needs. The
tree difference is the value of this experiment minus the value of
`wake-code-place-q4` at the same point. Now both experiments run on
`ws-up`, so the difference compares no Zephyr versions yet.

The study `zephyr-versions` owns this experiment. The checks of its
H1 read it. No other study imports it.

## Method

- Tree `ws-up`. Semaphore wake (`LATBENCH_WAKE_SEM`). 50000 samples per
  point.
- The points are the cube `place` x `anchor`, as in `wake-code-place-q4`.

## Axes

- **place**: `f0` and `f4` (`LATBENCH_CODE_FLASH_PAD`, pad 0 and
  4 bytes) give the tree difference in flash, for comparison. `r0` and
  `r4` (`LATBENCH_CODE_RAM`, pad 0 and 4 bytes) give the tree difference
  in RAM at two pads.
- **anchor**: `default` and `noslice`, as in `wake-code-place-q4`.
