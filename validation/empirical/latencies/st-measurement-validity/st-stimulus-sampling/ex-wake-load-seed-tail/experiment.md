# load-seed-tail

## What it measures

App `wake_latency`, metric `irq`: the tail of the IRQ latency with a
longer run and with other load seeds.

## Method

- Tree `ws-up`. The point of `stim-seed-1m` with the default stimulus
  seed: semaphore given from the wrapped ISR, 64 periodic load timers,
  hot code in the CCM SRAM.
- 1M samples per point, 4M for `default-4m`. 2048 fine bins and 2048
  coarse bins.
- No cube: each point changes one factor against the default point.
- Board time: about 40 min.

## Axes

- **load_seed**: the seed of the load timers
  (`LATBENCH_LOAD_TIMER_SEED`). `6a09e667` is the default.
  `90befffa` has the fewest ticks with >= 3 expiries. `78a5636f` is the
  only seed with a tick with 6 expiries, and it has the most ticks with
  >= 5. `c67178f2` has the most ticks with >= 3 expiries.
- **samples**: `1m` or `4m` (point `default-4m`). The 4M run is a long
  run against 4 stimulus seeds of 1M.
