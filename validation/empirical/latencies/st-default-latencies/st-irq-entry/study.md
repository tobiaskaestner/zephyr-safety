# irq-entry

## Background

This study measures the IRQ entry latency. The latency is the time from
the edge to the first instruction of the ISR. All experiments use the
app `irq_latency` on the board `nucleo_g474re`. The study measures four
interrupt paths:

- `stock`: the GPIO driver callback. This is the default path of the app.
- `wrapped`: an own ISR through `_isr_wrapper`.
- `direct`: an own direct ISR.
- `zli`: an own direct zero-latency ISR.

The question of the study is in `study.yaml`: how long is the latency
for each path, and where do its modes come from? The experiments test
three possible mechanisms for the modes and for the tail of the
distribution.

1. The wake-up of the CPU from WFI. When the CPU is idle, the idle
   thread runs and the CPU executes WFI. When the CPU is busy, the idle
   thread does not run, and the CPU does not execute WFI.
2. Flash or ART cache misses after other code ran. The main thread runs
   other code at each poll. The clock driver sets the flash wait states
   for the clock frequency. At 16 MHz the flash has 0 wait states, so a
   cache miss costs no time.
3. Time slicing. The busy thread is preemptible, so it has a slice
   timeout.

## Experiments

The study owns `irq-smoke` and `irq-checks-1m`. It reads
`irq-baseline-1m` with an import. The study `zephyr-versions` owns
`irq-baseline-1m`.

`irq-smoke` is the first check of the method. It measures the four paths
with the board defaults and an idle CPU. It also measures the direct
path with a busy CPU. The compare of `direct-busy` with `direct-idle`
shows if the WFI wake-up makes the second mode (H1 in `hypotheses.yaml`,
written 2026-10-24, before the run `irq-smoke/20261024T153130Z`). The
sample count and the stimulus are the defaults of the app.

`irq-baseline-1m` measures the same four paths as `irq-smoke`, with the
board defaults and an idle CPU. It has 1M samples per point, for plots
of the distribution and of its tail. It runs on the tree `ws-up`. Its
point ids are the same as in `irq-smoke`. Its point `direct-idle` is
the reference point of `irq-checks-1m`. The central result
`irq-entry-p99-direct` in `study.yaml` comes from this point. This
experiment stated no prediction before its run.

`irq-checks-1m` starts from two observations of `irq-smoke` on the
direct path. The first observation is a second mode (H2 in
`hypotheses.yaml` gives its offset and share). The second observation is
a larger tail with a busy CPU. The experiment checks two causes for
these observations: cache misses (H2) and time slicing (H3). Each point
changes one factor against `direct-idle` of `irq-baseline-1m`.
`busy-noslice` changes two factors.

The predictions for `irq-checks-1m` were written on 2026-10-24, before
the run `irq-checks-1m/20261024T163216Z` (dates from `hypotheses.yaml`):

- If cache misses make the second mode, the share of the mode follows
  the poll rate (`idle-poll10`, `idle-poll1000`).
- If cache misses make the second mode, the mode is not there at
  16 MHz (`idle-16mhz`). The point `idle-85mhz` is a clock between
  170 MHz and 16 MHz.
- If time slicing makes the larger tail, the tail of `busy-noslice`
  goes back to the idle level. The point `busy` shows the larger tail.

## References

- `hypotheses.yaml`: the hypotheses H1, H2 and H3, and their checks.
- `ex-irq-smoke/experiment.md`: the first check of the method. It is
  the source of the second mode and of the larger tail.
- `st-zephyr-versions/ex-irq-baseline-1m/experiment.md`: the same four
  paths with 1M samples, and the reference point `direct-idle`.
- `ex-irq-checks-1m/experiment.md`: the checks of the modes against
  `direct-idle`.
- `tests/benchmarks/irq_latency/Kconfig`: the paths and the defaults of
  the app.
- `tests/benchmarks/common/boards/nucleo_g474re/clocks/`: the clock
  overlays.
