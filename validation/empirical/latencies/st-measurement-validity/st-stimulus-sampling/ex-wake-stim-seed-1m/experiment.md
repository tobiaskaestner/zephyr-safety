# wake-stim-seed-1m

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`: the spread of the
results over different sequences of the random stimulus.

## Method

- Tree `ws-up`. The point `baseline-t64` of `wake-kconfig-1m`: semaphore
  given from the wrapped ISR, 64 periodic load timers, hot code in the
  CCM SRAM.
- 1M samples per point. 2048 fine bins and 2048 coarse bins.
- Board time: 8 points x (30 s + 1000000 x 300 us + 10 s), about 45 min.

## Axes

- **seed**: the stimulus seed (`LATBENCH_STIM_SEED`). It changes only
  the stimulus sequence. The load timers keep their own seed.
  `seed-default` is the default of the app, the seed of all earlier
  runs. `seed-6a09e667` .. `seed-1f83d9ab` are the 8 words of the
  SHA-256 start values, without the default.
