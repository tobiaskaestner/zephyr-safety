# systick-priority

## Background

This study measures how much of the IRQ tail under timer load comes from
the SysTick ISR. The question of the study is in `study.yaml`: does a
lower SysTick priority make the IRQ tail, the IRQ max and the ISR to
thread wake smaller?

In `wake-timers-1m`, the SysTick ISR makes the IRQ tail. The ISR runs
the callbacks of the load timers and restarts them. The p99.99 of the
IRQ latency is 5600 cycles at 64 timers and 25600 cycles at 256 timers.

The study uses these facts of the code:

1. The driver gives SysTick the same priority as the stimulus IRQ:
   SysTick and EXTI0 at priority 0. If both are pending, SysTick goes
   first, and EXTI0 cannot preempt it.
2. With `LATBENCH_SYSTICK_PRIO=1`, SysTick has priority 1. Then EXTI0
   can preempt the SysTick ISR outside its locked sections.
3. The locked sections of the SysTick ISR (timeout lock, clock lock)
   mask EXTI0 through BASEPRI at all priorities.
4. PendSV has a lower priority than SysTick at both priorities. Thus
   PendSV still waits for the SysTick ISR.

## Experiments

`wake-systick-prio-1m` measures the IRQ latency and the wake with 64 and 256
periodic load timers (10..100 ms). These loads gave the IRQ tail in
`wake-timers-1m`. Each load runs with SysTick at the same priority as
EXTI0 and at a lower priority. The experiment runs on two trees,
`ws-safety` and `ws-up`.

The study imports three experiments:

- `wake-timers-1m` (`load-scaling/timeout-queue-cost`): the IRQ tail
  with 0..256 periodic load timers and SysTick at the same priority as
  EXTI0.
- `wake-stim-seed-1m` and `wake-load-seed-tail`
  (`measurement-validity/stimulus-sampling`): the tail of the `t64`
  point over 8 stimulus seeds and 4 load seeds.

The predictions were written before the runs (dates from
`hypotheses.yaml`):

- H1: when the SysTick ISR has the same priority as EXTI0, the whole
  SysTick ISR delays the stimulus IRQ. Thus the IRQ tail grows with the
  number of periodic timers (written 2026-10-24, before
  `wake-timers-1m/20261024T225125Z`). The tail gets smaller by the
  unlocked part of the ISR when SysTick has a lower priority (written
  2026-10-25, before `systick-prio-1m/20261025T051643Z`).
- H2: a lower SysTick priority does not remove the delays in the locked
  sections and before PendSV. Thus the IRQ max and the `isr2thr` stay
  about the same (written 2026-10-25, before
  `systick-prio-1m/20261025T051643Z`).

The central result `systick-prio-tail` in `study.yaml` gives the p99.99
and the max for each point of `wake-systick-prio-1m`.

## References

- `hypotheses.yaml`: the hypotheses H1 and H2, and their checks.
- `ex-systick-prio-1m/experiment.md`: the SysTick priority points.
- `st-load-scaling/st-timeout-queue-cost/ex-wake-timers-1m/experiment.md`:
  the IRQ tail with load timers.
- `st-measurement-validity/st-stimulus-sampling/study.md`: the seeds of
  the `t64` tail.
- Open item L1 (`later.md`): SysTick priority lower than the device IRQ.
