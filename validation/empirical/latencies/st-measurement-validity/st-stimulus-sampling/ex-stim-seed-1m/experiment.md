# stim-seed-1m

## Question

How much does a result depend on the sequence of the random stimulus?

Each run before this experiment used the same stimulus seed, and the same
image gives the same histograms bin for bin. A repetition thus gives no
information about the spread of a result. A different seed does.

## Method

App `wake_latency` at the point `baseline-t64` of `wp3-wake-1m`:
semaphore given from the wrapped ISR, 64 periodic load timers, hot code in
the CCM SRAM. This point has tails from the SysTick ISR, so the seed has
an effect to measure. 1M samples per point.

The axis `seed` sets `LATBENCH_STIM_SEED`. It changes only the stimulus
sequence. The load timers keep their own seed.

| Point | Seed | Why |
|---|---|---|
| `seed-default` | the default of the app | The seed of all earlier runs. It connects this run to the night run of `wp3-wake-1m`. |
| `seed-6a09e667` .. `seed-1f83d9ab` | the 8 words of the SHA-256 start values, without the default | Seeds that nobody selected by hand. |

The image of this experiment is not the image of the night run: a new
`LAT META` line makes `stim_init()` 16 bytes longer, so the CCM code
after it moves by 16 bytes.

Board time: 8 points x (30 s + 1000000 x 300 us + 10 s), about 45 min.

## References

- Night run of `wp3-wake-1m`, `baseline-t64`: owned by `kconfig-factors`.
- Q4 code placement check: `st-measurement-validity/st-code-placement`.
