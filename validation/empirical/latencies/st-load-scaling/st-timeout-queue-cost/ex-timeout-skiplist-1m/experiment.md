# timeout-skiplist-1m

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`: as `timeout-backends-1m`,
for the SKIPLIST timeout queue backend.

## Method

- As `timeout-backends-1m`, but only in the tree `ws-up`: the SKIPLIST
  backend is only in this tree.

## Axes

- **backend**: one value, `skiplist` (`TIMEOUT_BACKEND_SKIPLIST`). The
  axis has the name of the axis of `timeout-backends-1m`.
