# load-seed-tail

## Question

What sets the tail of the IRQ latency: the run length, the stimulus seed
or the load timers?

`stim-seed-1m` showed that 8 stimulus seeds act as new independent
samples: the counts above each threshold agree with a Poisson
distribution. The model of the load timers (`scripts/benchmarks/loadmodel.py`)
says that the long SysTick ISRs come from the ticks on which several load
timers expire. `LATBENCH_LOAD_TIMER_SEED` sets these ticks. The stimulus
seed does not. Thus a new stimulus seed gives new edges on the same
ticks, but a longer run or a new load seed gives new ticks.

## Method

App `wake_latency` at the point of `stim-seed-1m` (default stimulus
seed). Each point changes one factor against that point.

| Point | `load_seed` | `samples` | Why |
|---|---|---|---|
| `default-4m` | 6a09e667 (default) | 4M | A long run against 4 stimulus seeds of 1M. |
| `lseed-90befffa` | 90befffa | 1M | The fewest ticks with >= 3 expiries. |
| `lseed-78a5636f` | 78a5636f | 1M | The only seed with a tick with 6 expiries, and the most ticks with >= 5. |
| `lseed-c67178f2` | c67178f2 | 1M | The most ticks with >= 3 expiries. |

The load seeds come from `loadmodel.py scan` over the 64 SHA-256 round
constants, by the rule in the table. Nobody selected them by hand.

Ticks with >= k expiries in a run of 1M samples (311 s), from the model:

| Load seed | >= 2 | >= 3 | >= 4 | >= 5 | >= 6 |
|---|---|---|---|---|---|
| 0x6a09e667 (default) | 33484 | 1518 | 39 | 0 | 0 |
| 0x90befffa | 23515 | 948 | 33 | 0 | 0 |
| 0x78a5636f | 43903 | 2674 | 125 | 8 | 1 |
| 0xc67178f2 | 52259 | 3608 | 209 | 9 | 0 |

The default point with 4M samples (1245 s) has 6142 ticks with >= 3
expiries, 199 with >= 4, and 1 tick with 5 expiries (at 920 s).

A new `LAT META` line moves the CCM code after `load_print()`. Thus this
image acts as a new stimulus seed against `stim-seed-1m`. Comparisons
with `stim-seed-1m` are for the statistics, not bin for bin.

Board time: 4M point 30 s + 1200 s + 15 s; three 1M points 3 x 340 s.
About 40 min.

## References

- `scripts/benchmarks/loadmodel.py`: the model of the load timer expiries.
- `stim-seed-1m.md`: the reference point and the 8 stimulus seeds.
