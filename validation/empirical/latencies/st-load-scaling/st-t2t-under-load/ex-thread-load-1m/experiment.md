# thread-load-1m

## What it measures

App `thread_latency`, metric `t2t`: the thread to thread wake latency of
three primitives with periodic load timers and sleeper threads. The
points test the model of the study (`../study.md`):

```text
t2t(load) = t2t_fast(no load) + c * n
```

`n` is the number of timeouts that expire before the new slice deadline.

## Method

- Tree `ws-up`. The giver thread wakes the taker thread through the
  primitive under test.
- Random stimulus interval 50..150 us. Hot code in the CCM SRAM.
- 1M samples per point. 2048 fine bins and 2048 coarse bins.
- The points are the cube `primitive` x `load` (id
  `<primitive>-<load>`) and three control points without time slicing.

## Axes

- **primitive**: `sem`, `mutex` or `msgq` (`LATBENCH_T2T_SEM`, `_MUTEX`,
  `_MSGQ`).
- **load**: `none` is the reference of each primitive. `t16`, `t64` and
  `t256` are 16, 64 and 256 periodic load timers
  (`LATBENCH_LOAD_TIMERS`): `n` = 7.5, 30, 120. `sl8` and `sl64` are 8
  and 64 sleeper threads (`LATBENCH_LOAD_THREAD_SLEEPER`,
  `LATBENCH_LOAD_THREADS`): `n` = 8, 64. The axis has no numbers: its
  values are timers and threads, and `n` is not a setting.
- **slicing**: `default` for the cube points. `noslice`
  (`TIMESLICING=n`) for the control points `sem-none-noslice`,
  `sem-t256-noslice` and `sem-sl64-noslice`.
