# thread-switch

## What it measures

App `thread_latency`, metric `t2t`: the thread to thread wake latency
(M3) of the semaphore and the mutex, with the legacy thread switch
(PendSV) and with the new arch interface (`USE_SWITCH=y`), on both
trees.

## Method

- Trees `ws-safety` and `ws-up`. 1M samples per point.
- Random stimulus interval 50..150 us. Histograms with 2048 fine and
  2048 coarse bins. These are the settings of `thread-baseline-1m`.
- The points are the cube `primitive` x `arch`.

## Axes

- **primitive**: `sem` (`LATBENCH_T2T_SEM`) or `mutex`
  (`LATBENCH_T2T_MUTEX`).
- **arch**: `legacy` is the thread switch through PendSV. The legacy
  points are the reference from the same session, with the same
  settings as `sem` and `mutex` in `thread-baseline-1m`. `switch` is the
  new arch interface (`common/conf/use_switch.conf`).
