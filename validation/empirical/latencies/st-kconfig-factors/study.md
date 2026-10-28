# kconfig-factors

## Background

This study measures how the Kconfig options of the WP3 ranking change
the three latencies: the IRQ entry (`irq`), the ISR to thread wake
(`isr2thr`) and the thread to thread latency (`t2t`). The question of
the study is in `study.yaml`. The options come from the ranked list of
the Kconfig factors in `wp3-kconfig-ranking.md` (project notes, not in
this repository).

Each variant changes one Kconfig factor against the defaults of the
apps. The point `baseline` has these defaults. Each check compares a
variant with the point `baseline` of the same run. `wp3-variants.md`
describes the variants, the defaults and two Kconfig traps one time for
the three experiments.

All three experiments run on the tree `ws-up`, with 1M samples per
point. The hot code is in the CCM SRAM (`LATBENCH_CODE_RAM`, see
`st-measurement-validity/st-code-placement`).

The design uses these facts of the code:

- On the IRQ entry path, the kernel does no scheduling and saves no FP
  context. Thus the scheduler variants and `fpu-sharing` are references
  for "no change" in `irq-kconfig-1m`.
- Without `TICKLESS_KERNEL`, `sys_clock_set_timeout()` returns at once
  (ws-up `drivers/timer/system_timer_generic.h:650`). Thus the slice
  reset never reprograms the SysTick in `tickless-off` and
  `tickless-off-100`. The slice walk over the timeouts stays.

## Experiments

This study owns the three experiments. It has no hypotheses. Each
sub-study has the hypotheses of one question and imports the three
experiments.

`irq-kconfig-1m` measures the IRQ entry on the wrapped ISR path, with an
idle CPU and a random stimulus interval of 100..500 us. It has the 11
variants with no load. Four more points have 64 load timers:

- `baseline-t64` is the reference for the other points with 64 load
  timers.
- `ticks1000-t64`: 1000 ticks/s puts the expiries of the timers into
  fewer ticks.
- `tickless-off-t64`: a SysTick ISR comes every 100 us, also when no
  timer expires.
- `tickless-off-100-t64`: a SysTick ISR every 10 ms handles the
  expiries of 10 ms.

`wake-kconfig-1m` measures the wake by a semaphore from the wrapped ISR. It
has the 11 variants with no load. Three points have 16 busy threads,
with priority 5. This priority is lower than the priority of the woken
thread.

- `baseline-busy16` is the reference for the other points with 16 busy
  threads.
- `scalable-busy16` asks: does the cost of the red-black tree grow with
  the number of threads?
- `multiq-busy16` asks the same for one list for each priority.

Four points of `wake-kconfig-1m` have 64 load timers:

- `baseline-t64` is the reference for the other points with 64 load
  timers.
- `ticks1000-t64`: the slice walk over the timeouts at 1000 ticks/s.
- `tickless-off-t64`: the slice walk without the SysTick reprograms.
- `tickless-off-100-t64`: the same at 100 ticks/s.

The review of 2026-10-25, §5, gives the cost of a sliced busy thread for
each wake, from `wake-threads-1m` (2..64 busy threads).

`thread-kconfig-1m` measures the wake by a semaphore from a thread: the taker
thread preempts the giver thread. The stimulus interval is 50..150 us.
It has the 11 variants with no load. Each sample has one thread switch.
The variant `tickless-off` is the strongest test of the cause of the two
modes of the baseline. It removes the SysTick reprograms, but it keeps
the slice walk.

The predictions were written on 2026-10-25, before the runs
`wp3-t2t-1m/20261025T203235Z`, `wp3-wake-1m/20261025T205806Z` and
`wp3-irq-1m/20261025T223624Z` (dates from the `hypotheses.yaml` files of
the sub-studies). The four sub-studies are:

- `scheduler`: the effect of `SCHED_SCALABLE` and `SCHED_MULTIQ`, with
  no load and with 16 busy threads, and the cost of 16 busy threads for
  the wake.
- `tick-mode`: the effect of the tickless kernel and of the tick rate.
  It asks if the SysTick reprogram of the slice reset makes the two
  modes of the wake and the clock drift. It gives the central result
  `tick-reprogram-modes`.
- `code-generation`: the effect of `SPEED_OPTIMIZATIONS`, `ASSERT`
  (with and without `SPIN_VALIDATE`) and `FPU_SHARING`.
- `stack-guard`: the cost of the MPU stack guard.

The central results `irq-ranking`, `wake-ranking` and `t2t-ranking` sort
the variants by their change against the baseline of the same run, for
the p50 and the p99.

## References

- `wp3-variants.md`: the variants, the defaults and the Kconfig traps.
- `ex-wp3-irq-1m/experiment.md`, `ex-wp3-wake-1m/experiment.md`,
  `ex-wp3-t2t-1m/experiment.md`: the three experiments.
- `st-scheduler/study.md`, `st-tick-mode/study.md`,
  `st-code-generation/study.md`, `st-stack-guard/study.md`: the
  sub-studies.
- `st-measurement-validity/st-code-placement`: the hot code in the CCM
  SRAM.
- `st-default-latencies/st-thread-to-thread/study.md`: the two modes of
  the thread to thread latency.
- `st-load-scaling/st-timeout-queue-cost/ex-wake-threads-1m/experiment.md`:
  the wake with 2..64 busy threads.
- Review of 2026-10-25, §5 (project notes, not in this repository): the
  cost of a sliced busy thread for each wake, from `wake-threads-1m`.
- `wp3-kconfig-ranking.md` (project notes, not in this repository): the
  ranked list of the Kconfig factors, the source of the variants.
