# thread2thread-switch

## Question

How long is the thread to thread wake (M3) with the new arch interface
(`USE_SWITCH=y`), on both trees? Does it have the same two modes as with
PendSV?

With `USE_SWITCH=y`, a thread switch on Cortex-M is `arch_switch()`
inline in `z_swap()`, in thread mode, without PendSV.

## Method

App `thread_latency`, trees `ws-safety` and `ws-up`. 1M samples per
point. Random stimulus interval 50..150 us. Histograms with 2048 fine
and 2048 coarse bins. These are the settings of `thread2thread-1m`.

The points are the cube `primitive` x `arch`.

| Point | Settings | Why |
|---|---|---|
| `sem-legacy` | `LATBENCH_T2T_SEM`, PendSV | The reference from the same session. Same settings as `sem` in `thread2thread-1m`. |
| `sem-switch` | `LATBENCH_T2T_SEM`, `common/conf/use_switch.conf` | The semaphore with the new arch interface. |
| `mutex-legacy` | `LATBENCH_T2T_MUTEX`, PendSV | The reference from the same session. Same settings as `mutex` in `thread2thread-1m`. |
| `mutex-switch` | `LATBENCH_T2T_MUTEX`, `use_switch.conf` | The mutex with the new arch interface. |

## References

- `thread2thread-1m.md`: the legacy points of all kernel objects.
- `default-latencies/isr-to-thread/wake-anchors-1m.md`: the cost of `USE_SWITCH=y` for the ISR wake.
- `update_cache()` in `kernel/sched.c`: the slice reset.
