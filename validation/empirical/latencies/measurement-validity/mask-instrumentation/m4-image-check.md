# m4-image-check

## Question

Does the tree `ws-up-irqoff` give the image of `ws-up` when the M4 hooks
are off (`CONFIG_ARM_IRQ_MASK_HOOKS=n`)?

The hooks must not change the code when they are off. Only then is a
latency of `ws-up-irqoff` without hooks also a latency of `ws-up`.

## Method

Build only: `run.py --build-only --keep-build`. There is no board run.

App `wake_latency`, semaphore given from the wrapped ISR, 1M samples,
latency histograms of 2048 fine and 2048 coarse bins. Each point is built
on `ws-up` and on `ws-up-irqoff`, with the hooks off. Then the two images
of each point are compared.

| Point | Settings | Why |
|---|---|---|
| `t0-default` | no load timers, time slicing on | A point of `wake-timers-1m`, with the same settings. |
| `t256-default` | 256 periodic load timers, time slicing on | A point of `wake-timers-1m`, with the same settings. |

The version strings (`BUILD_VERSION`: the `git describe` of each Zephyr
tree) can differ between the two trees.

## References

- `doc/benchmark-guide/m4.rst`: the M4 method and the hooks.
- `load-scaling/wake-timers-1m.md`: the source of the two points.
- `claude/latency-benchmarks/m4-design.md` §4 (outside this repository):
  the build checks.
