# t2t-load-1m

## Question

Does the thread to thread wake latency (`t2t`) grow linearly with the
load, and with which variable? The question at the start of the study
was: does the latency grow with the number of timers, O(#timers), or
with the number of threads, O(#threads)?

## Method

The model of the experiment comes from the ISR to thread wake (review
2026-10-25, §4 and §5):

```text
t2t(load) = t2t_fast(no load) + c * n
```

- `n` is the number of timeouts that expire before the new slice
  deadline (20 ms after the reset). In each sample, the give resets the
  time slice of the taker (`update_cache()`). The DLIST insert walks
  over these `n` timeouts with the timeout lock held.
- `c` is about 20..25 cycles per node. The wake data gave 24.5 cycles
  per sleeper and about 20 cycles per timer node.
- Periodic timers (10..100 ms): `n` is about 0.47 x T, thus 7.5, 30 and
  120 for T = 16, 64 and 256.
- Sleepers (1..20 ms, all shorter than the slice): `n` = N, thus 8 and
  64.

App `thread_latency`: the giver thread wakes the taker thread through the
primitive under test. Random stimulus interval 50..150 us. Hot code in
the CCM SRAM. 1M samples per point. 2048 fine bins and 2048 coarse bins.

The points are the cube `primitive` x `load` (id `<primitive>-<load>`)
and three control points without time slicing.

| Point | Settings | Why |
|---|---|---|
| `sem-*`, `mutex-*`, `msgq-*` | `LATBENCH_T2T_SEM`, `_MUTEX`, `_MSGQ` | The model says that the walk is in the scheduler, not in the primitive. Three primitives show if the slope is the same. |
| `*-none` | no load | The reference of each primitive. |
| `*-t16`, `*-t64`, `*-t256` | `LATBENCH_LOAD_TIMERS` = 16, 64, 256 | Periodic load timers: `n` = 7.5, 30, 120. |
| `*-sl8`, `*-sl64` | `LATBENCH_LOAD_THREAD_SLEEPER`, `LATBENCH_LOAD_THREADS` = 8, 64 | Sleeper threads: `n` = 8, 64. |
| `sem-none-noslice`, `sem-t256-noslice`, `sem-sl64-noslice` | `TIMESLICING=n` | The control: without time slicing, the give inserts no slice timeout. |

The axis `load` has no numbers: its values are timers and threads, and
the model variable `n` is not a setting. The control points have the
axis value `slicing: noslice`. All other points have `slicing: default`.

## References

- Review 2026-10-25 §4 (timers) and §5 (threads): the model of the slice
  reset.
- `wake-timers-1m.md`, `wake-threads-1m.md`: the wake data for `c`.
