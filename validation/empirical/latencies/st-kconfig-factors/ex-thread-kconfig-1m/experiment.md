# thread-kconfig-1m

## What it measures

App `thread_latency`, metric `t2t`: the thread to thread latency for
each WP3 Kconfig factor, against the point `baseline` of the same run.

## Method

- Tree `ws-up`. Semaphore: the taker thread preempts the giver thread.
  Hot code in the CCM SRAM.
- Random stimulus interval 50..150 us. 1M samples per point, 2048 fine
  and 2048 coarse histogram bins.
- The points are the 11 values of the axis `variant`, with no load. Each
  sample has one thread switch.

## Axes

- **variant**: one Kconfig factor at a time against the defaults of the
  app. `../wp3-variants.md` gives the variants, the defaults and the
  Kconfig traps. `irq-kconfig-1m` and `wake-kconfig-1m` have the same variants.
