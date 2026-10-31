# stimulus-sampling

## Background

This study checks how the random stimulus samples the latency
distribution. The question of the study is in `study.yaml`: does the
random stimulus sample the distribution evenly over the kernel tick? How
many samples, stimulus seeds and load seeds does a value from the p50
to the max need?

The study has two parts:

1. The tick phase. The apps record each sample in one of 64 bins by the
   tick phase of the stimulus edge. The random stimulus (interval
   100..500 us) is the stimulus of all other experiments. A fixed period
   of 300 us + 1 cycle is a scan: 300 us is 3 ticks, so the tick phase
   moves by 1 cycle per edge. The scan covers the full tick about 59
   times in 1M samples.
2. The seeds. Each run before `wake-stim-seed-1m` used the same stimulus
   seed, and the same image gives the same histograms bin for bin. A
   repetition thus gives no information about the spread of a result. A
   different seed does. `LATBENCH_STIM_SEED` changes only the stimulus
   sequence. The load timers keep their own seed
   (`LATBENCH_LOAD_TIMER_SEED`).

The model of the load timers (`scripts/probatrix/benchmarks/loadmodel.py`) says
that the long SysTick ISRs come from the ticks on which several load
timers expire. `LATBENCH_LOAD_TIMER_SEED` sets these ticks. The stimulus
seed does not. Thus a new stimulus seed gives new edges on the same
ticks, but a longer run or a new load seed gives new ticks.

## Experiments

`irq-phase-1m` asks: does the random stimulus cover the kernel tick
evenly? Where in the tick do the second mode and the tail of the IRQ to
ISR latency come from? It uses the direct ISR path of `irq_latency`.

`wake-phase-1m` asks: does the tick phase of the stimulus edge decide
between the two modes of the ISR to thread wake latency (`isr2thr`)?
`wake-isr-1m` showed two modes, 80 % and 20 % of the samples, 310 cycles
apart. The experiment uses the same method as `irq-phase-1m`.

`irq-phase-1m` and `wake-phase-1m` stated no prediction before their
runs. The coverage is the central result `phase-coverage`.

`wake-stim-seed-1m` asks: how much does a result depend on the sequence of
the random stimulus? It runs at the point `baseline-t64` of
`wake-kconfig-1m` (semaphore from the wrapped ISR, 64 periodic load timers,
hot code in the CCM SRAM). This point has tails from the SysTick ISR,
so the seed has an effect to measure. The default seed is the seed of
all earlier runs. It connects this run to the night run of
`wake-kconfig-1m`. The other seeds are the 8 words of the SHA-256 start
values, without the default. Nobody selected them by hand. The board time is about 45 min: 8 points
x (30 s + 1000000 x 300 us + 10 s).

The image of `wake-stim-seed-1m` is not the image of the night run. A new
`LAT META` line makes `stim_init()` 16 bytes longer, so the CCM code
after it moves by 16 bytes. The study `code-placement` uses this shift
as a check (H2 k there).

`wake-load-seed-tail` asks: what sets the tail of the IRQ latency, the run
length, the stimulus seed or the load timers? `wake-stim-seed-1m` showed
that 8 stimulus seeds act as new independent samples: the counts above
each threshold agree with a Poisson distribution. The experiment runs at
the point of `wake-stim-seed-1m` with the default stimulus seed. Each point
changes one factor against that point. The load seeds come from
`loadmodel.py scan` over the 64 SHA-256 round constants, by a rule for
each seed. Nobody selected them by hand.

Ticks with >= k expiries in a run of 1M samples (311 s), from the model:

| Load seed | >= 2 | >= 3 | >= 4 | >= 5 | >= 6 |
|---|---|---|---|---|---|
| 0x6a09e667 (default) | 33484 | 1518 | 39 | 0 | 0 |
| 0x90befffa | 23515 | 948 | 33 | 0 | 0 |
| 0x78a5636f | 43903 | 2674 | 125 | 8 | 1 |
| 0xc67178f2 | 52259 | 3608 | 209 | 9 | 0 |

The default point with 4M samples (1245 s) has 6142 ticks with >= 3
expiries, 199 with >= 4, and 1 tick with 5 expiries (at 920 s).

A new `LAT META` line moves the CCM code after `load_print()`. Thus the
image of `wake-load-seed-tail` acts as a new stimulus seed against
`wake-stim-seed-1m`. Comparisons with `wake-stim-seed-1m` are for the statistics,
not bin for bin. The board time is about 40 min: the 4M point
30 s + 1200 s + 15 s, the three 1M points 3 x 340 s.

The predictions were written on 2026-10-26, before the runs
`stim-seed-1m/20261026T155715Z` and `load-seed-tail/20261026T181105Z`
(dates from `hypotheses.yaml`):

- H1: stimulus seeds act as independent samples of one distribution.
  The seed changes which edges meet a SysTick ISR, not the behavior of
  the kernel. A value up to the p99.99 is stable over the seeds. The
  max is not.
- H2: a long run gives the same tail as several stimulus seeds of the
  same total length. The counts above a threshold scale with the number
  of ticks with many expiries.
- H3: the IRQ tail comes from the ticks on which several load timers
  expire. Thus the load seed, which sets these ticks, sets the tail.

A person confirms the central result `tail-needs-seeds` from H1, H2 and
H3. `report.ipynb` is the report template of the study.

## References

- `hypotheses.yaml`: the hypotheses H1, H2 and H3, and their checks.
- `ex-irq-phase-1m/experiment.md`, `ex-wake-phase-1m/experiment.md`:
  the tick phase.
- `ex-wake-stim-seed-1m/experiment.md`: the 8 stimulus seeds.
- `ex-wake-load-seed-tail/experiment.md`: the run length and the load seeds.
- `scripts/probatrix/benchmarks/loadmodel.py`: the model of the load timer
  expiries.
- `st-default-latencies/st-isr-to-thread/ex-wake-isr-1m/experiment.md`:
  the two modes.
- Night run of `wake-kconfig-1m`, `baseline-t64`: owned by
  `kconfig-factors`.
- `st-measurement-validity/st-code-placement/study.md`: the Q4 code
  placement check.
