# scheduler

## Background

This study measures how the scheduler variants change the IRQ entry, the
ISR to thread wake and the thread to thread latency. The question of the
study is in `study.yaml`. It also asks how much 16 busy threads add to
the wake.

The default of the apps is `SCHED_SIMPLE`, a run queue as a sorted list.
The study tests two other run queues:

- `scalable` (`SCHED_SCALABLE=y`): the run queue is a red-black tree,
  with a cost of log N.
- `multiq` (`SCHED_MULTIQ=y`): the run queue is one list for each
  priority.

The IRQ entry path has no scheduler.

The busy threads have priority 5, lower than the woken thread. Thus the
sorted insert of `SCHED_SIMPLE` stops at once. With time slicing, the
kernel slices the busy thread. This adds one slice abort and one add for
each wake (review of 2026-10-25, §5).

## Experiments

This study owns no experiment. It imports `irq-kconfig-1m`, `wake-kconfig-1m`
and `thread-kconfig-1m` from the parent study `kconfig-factors`. The checks
compare `scalable` and `multiq` with `baseline` in all three
experiments. In `wake-kconfig-1m`, they also compare `scalable-busy16` and
`multiq-busy16` with `baseline-busy16`.

The predictions were written on 2026-10-25, before the runs
`wp3-t2t-1m/20261025T203235Z`, `wp3-wake-1m/20261025T205806Z` and
`wp3-irq-1m/20261025T223624Z` (dates from `hypotheses.yaml`):

- H1: `SCHED_SCALABLE` adds a constant 50..200 cycles to the ISR to
  thread wake and to the thread to thread latency, also with 16 busy
  threads. It adds nothing to the IRQ entry. `SCHED_MULTIQ` changes the
  wake paths by less than 30 cycles, and the IRQ entry by at most
  2 cycles.
- H2: 16 busy threads add a constant cost of about 400 cycles to the
  wake. The cost comes from the slice of the busy thread, not from the
  ready queue. Thus it does not depend on the number of busy threads.
  `wake-kconfig-1m` has 16 busy threads only. `wake-threads-1m` has 2..64.

This study has no central result of its own. The rankings of the parent
study give the measured change of each variant.

## References

- `hypotheses.yaml`: the hypotheses H1 and H2, and their checks.
- `../wp3-variants.md`: the variants.
- `../study.md`: the three experiments.
- Review of 2026-10-25, §5 (project notes, not in this repository): the
  cost of a sliced busy thread for each wake.
- `st-zephyr-versions/ex-wake-threads-1m/experiment.md`:
  the wake with 2..64 busy threads.
