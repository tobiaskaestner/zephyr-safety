# tail-witnesses

## Background

A histogram gives the size of the tail, but not its cause. The phase
histograms of the study give the position of a sample in the kernel
tick, but not the event that delayed it. The upstream interrupt
benchmark (Zephyr PR 117170) reads a few counters for each outlier: the
DWT exception counter, the tick count and a load counter. On our board
this named the cause of each outlier of the PR runs.

The option `LATBENCH_TAIL` adds such witnesses to our apps: a table of
the largest samples, with the counters of a window from the arm of the
stimulus to the end of the sample (explanation page of the guide, tail
witnesses). `scripts/benchmarks/tails.py` gives the cause of each row.

A witness is useful only if three things are true:

1. It does not change the latency that it describes (H1). The mark runs
   before the stimulus and the add after the end time stamp. The option
   adds code, so the other code moves; thus the check uses the hot code
   in RAM.
2. Its cost is small (H2).
3. Its labels are correct. H3 tests the cause of the idle tail, which
   the upstream benchmark found on another board: the SysTick ISR. H4
   tests the new label `systick-reprogram` against a configuration in
   which it must not occur.

## Experiments

- `irq-witness-1m`: the entry latency (direct, idle) with and without
  witnesses, without load and with 16 load timers. It tests H1 a, b, H2
  and H3.
- `wake-witness-250k`: the wake latency (semaphore) with and without
  witnesses, with and without time slicing. It tests H1 c and H4.

The first run of `wake-witness-250k` found the wake path slower with the
witnesses (H1 c wrong). The cause was the data layout of that revision,
not the witness code: the sub-study `code-placement` (H3, experiments
`wake-data-place-250k` and `wake-witness-bss-250k`) tests it.

## References

- Explanation page of the guide: tail witnesses.
- Comparison of Zephyr PR 117170 with the study (agent notes), ideas 3
  and 4; PR commit 3fe87c6 (idle tail on the MCXN947).
- Manual quick checks of 2026-10-29 and 2026-10-30 (run-log of the agent
  notes; not data).
