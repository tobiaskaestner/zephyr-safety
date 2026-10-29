# irq-scenarios

## Background

The study measured the IRQ entry from the edge (`st-irq-entry`) and the
wake of a thread (`st-isr-to-thread`). The upstream interrupt benchmark
(Zephyr PR 117170) has four more scenarios: the time from `irq_unlock()`
to the ISR of a pending interrupt, the entry of an ISR that preempts a
lower-priority ISR, the exit to the interrupted thread, and the cost of
back-to-back ISRs. The choice `LATBENCH_IRQ_SCENARIO` of `irq_latency`
adds these scenarios. The app page (section Scenarios) defines each span
and compares it with the upstream span.

The unlock scenario is a direct check of a part of `st-mask-time`: the
mask time of a critical section delays a pending interrupt, but the
unlock itself can add a cost. It also tests which exception runs first
when SysTick became pending during the lock.

Numbers of the PR runs on the same board (p50, cycles, regular ISR,
flash, without slicing): `locked_unlock_to_isr` 87..112,
`nested_preempt` 77, `exit_resume_interrupted` 56..69,
`throughput_round_trip` 102..142, `entry_trigger_to_isr` 107..128,
`entry_direct_isr` 50..72. The PR spans include a DWT read with
barriers, a handler pointer and a control subtraction (app page).

## Experiments

- `irq-scenarios-1m`: the four scenarios and the entry (busy thread,
  edge and software trigger) as their reference, for the paths
  `wrapped` and `direct`, with the hot code in RAM and witness tables.
  It tests H1 to H4.

## References

- App page of `irq_latency`, section Scenarios.
- Comparison of Zephyr PR 117170 with the study (agent notes,
  `pr-117170-comparison.md`), sections 3 and 5.4.
- ARMv7-M Architecture Reference Manual, B1.5.4 (exception priorities
  and the order of pending exceptions of the same priority).
- Manual quick checks of 2026-10-30 (run-log of the agent notes; not
  data).
