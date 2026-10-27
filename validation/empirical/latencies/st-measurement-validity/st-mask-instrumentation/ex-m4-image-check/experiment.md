# m4-image-check

## What it measures

App `wake_latency`, no metric (build only): it compares the image of
`ws-up-irqoff` with the image of `ws-up` when the M4 hooks are off
(`CONFIG_ARM_IRQ_MASK_HOOKS=n`).

## Method

- Build only: `run.py --build-only --keep-build`. There is no board run.
- Semaphore given from the wrapped ISR, 1M samples, latency histograms
  of 2048 fine and 2048 coarse bins.
- Each point is built on `ws-up` and on `ws-up-irqoff`, with the hooks
  off. Then the two images of each point are compared.
- The points are the cube `timers` x `anchor`: `t0-default` and
  `t256-default`.

## Axes

- **timers**: `t0` has no load timers. `t256` has 256 periodic load
  timers. Each point is a point of `wake-timers-1m`, with the same
  settings.
- **anchor**: one value, `default` (time slicing on). The axis keeps the
  point ids of `wake-timers-1m`.
