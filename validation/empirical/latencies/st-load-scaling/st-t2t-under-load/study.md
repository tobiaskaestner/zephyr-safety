# t2t-under-load

## Background

This study measures how the thread to thread wake latency (`t2t`) grows
with the load. The question at the start of the study was: does the
latency grow with the number of timers, O(#timers), or with the number
of threads, O(#threads)? The question of the study is now in
`study.yaml`: does the `t2t` p50 follow the number `n` of timeouts that
expire before the slice deadline, with one slope for sem, mutex and
msgq? Does its tail grow with the load?

The model comes from the ISR to thread wake (review 2026-10-25, §4 and
§5):

```text
t2t(load) = t2t_fast(no load) + c * n
```

- `n` is the number of timeouts that expire before the new slice
  deadline (20 ms after the reset). In each sample, the give resets the
  time slice of the taker (`update_cache()`). The reset inserts a
  timeout. The DLIST insert walks over these `n` timeouts with the
  timeout lock held.
- `c` is about 20..25 cycles per node. The wake data gave 24.5 cycles
  per sleeper and about 20 cycles per timer node.
- Periodic timers (10..100 ms): `n` is about 0.47 x T. Thus `n` is 7.5,
  30 and 120 for T = 16, 64 and 256.
- Sleepers (1..20 ms, all shorter than the slice): `n` = N. Thus `n` is
  8 and 64.

Without load, two SysTick reprograms give the slow mode. When a timeout
comes before the slice deadline, the slice abort and add do not
reprogram SysTick. The model says that the walk is in the scheduler,
not in the primitive. Without time slicing, the give inserts no slice
timeout.

## Experiments

`thread-load-1m` is the only experiment of the study. It measures three
primitives, sem, mutex and msgq. The three primitives show if the slope
is the same for all. Each primitive has a reference point without load.
Three control points without time slicing check that the slice reset is
the cause of the growth.

The predictions were written on 2026-10-25, before the run
`t2t-load-1m/20261025T193636Z` (dates from `hypotheses.yaml`):

- H1: without load, the `t2t` has two modes: about 20 % fast and 80 %
  slow, about 640 cycles apart. Under load, the `t2t` has one mode, and
  its p50 is linear in `n`, with the same slope `c` for the three
  primitives. Without time slicing, the p50 does not grow with the
  load.
- H2: the tail (p99.99) of `t2t` grows with the number of timers and
  with the number of sleepers. The SysTick ISR preempts the threads, as
  in the wake data.

The central result `t2t-grows-with-n` in `study.yaml` comes from H1.

## References

- `hypotheses.yaml`: the hypotheses H1 and H2, and their checks.
- `ex-thread-load-1m/experiment.md`: the load points and the control
  points.
- Review 2026-10-25 §4 (timers) and §5 (threads): the model of the slice
  reset.
- `st-zephyr-versions/ex-wake-timers-1m/experiment.md`,
  `st-zephyr-versions/ex-wake-threads-1m/experiment.md`:
  the wake data for `c`.
