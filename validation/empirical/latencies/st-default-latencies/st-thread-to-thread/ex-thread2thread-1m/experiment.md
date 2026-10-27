# thread2thread-1m

## What it measures

App `thread_latency`, metric `t2t`: the thread to thread wake latency
(M3) for each kernel object, with the board and kernel defaults, on
both trees.

## Method

- Trees `ws-safety` and `ws-up`. 1M samples per point.
- Random stimulus interval 50..150 us. Histograms with 2048 fine and
  2048 coarse bins.
- The ISR wakes the giver thread (priority 2) at a random time. The
  giver wakes the taker through the kernel object. `t2t` is the time
  from the wake call to the taker.
- The points are the 11 points of the axis `primitive`, plus two
  explicit points without preemption.

## Axes

- **primitive**: the kernel object, `LATBENCH_T2T_<OBJECT>`: `sem`,
  `mutex`, `condvar`, `event`, `msgq`, `fifo`, `lifo`, `stack`, `poll`,
  `work`, `wakeup`.
- **preemption**: `preempt` for the 11 points of `primitive`: the taker
  has priority 1 and preempts the giver. `nopreempt`
  (`LATBENCH_T2T_PREEMPT: n`, points `sem-nopreempt` and
  `mutex-nopreempt`): the taker has priority 3.
