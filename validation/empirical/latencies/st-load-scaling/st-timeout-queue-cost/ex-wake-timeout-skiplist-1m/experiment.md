# wake-timeout-skiplist-1m

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`: as `wake-timeout-backends-1m`,
for the SKIPLIST timeout queue backend.

## Method

- As `wake-timeout-backends-1m`, on the tree `ws-up`. The SKIPLIST
  backend is not in all Zephyr versions. Thus it is not a point of
  `wake-timeout-backends-1m`, because that experiment can run on more
  than one tree.

## Axes

- **backend**: one value, `skiplist` (`TIMEOUT_BACKEND_SKIPLIST`). The
  axis has the name of the axis of `wake-timeout-backends-1m`.
