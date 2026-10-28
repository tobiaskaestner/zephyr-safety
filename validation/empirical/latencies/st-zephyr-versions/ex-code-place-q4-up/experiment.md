# code-place-q4-up

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`, and the clock drift:
the points of `code-place-q4` that the tree comparison needs, on the
tree `ws-up`. The tree difference is the value of `ws-up` minus the
value of `ws-safety` (`code-place-q4`) at the same point.

## Method

- Tree `ws-up`. Semaphore wake (`LATBENCH_WAKE_SEM`). 50000 samples per
  point.
- The points are the cube `place` x `anchor`, as in `code-place-q4`.

## Axes

- **place**: `f0` and `f4` (`LATBENCH_CODE_FLASH_PAD`, pad 0 and
  4 bytes) give the tree difference in flash, for comparison. `r0` and
  `r4` (`LATBENCH_CODE_RAM`, pad 0 and 4 bytes) give the tree difference
  in RAM at two pads.
- **anchor**: `default` and `noslice`, as in `code-place-q4`.
