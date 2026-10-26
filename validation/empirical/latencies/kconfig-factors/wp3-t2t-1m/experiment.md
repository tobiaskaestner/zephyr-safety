# wp3-t2t-1m

## Question

How does each WP3 Kconfig factor change the thread to thread latency
(`t2t`), against the point `baseline` of the same run?

## Method

App `thread_latency`, semaphore: the taker thread preempts the giver
thread. Hot code in the CCM SRAM. Random stimulus interval 50..150 us.
1M samples per point, 2048 fine and 2048 coarse histogram bins.

The axis `variant` changes one Kconfig factor at a time against the
defaults of the app. `../wp3-variants.md` gives the variants, the defaults
and the Kconfig traps. The experiments `wp3-irq-1m` and `wp3-wake-1m`
have the same variants.

| Point | Settings | Why |
|---|---|---|
| `baseline` .. `no-mpu-guard` | the 11 values of the axis `variant`, no load | Each factor alone, with no load. |

Each sample has one thread switch.

The variant `tickless-off` is the strongest test of the cause of the two
modes of the baseline. It removes the SysTick reprograms, but it keeps
the slice walk.

## References

- `../wp3-variants.md`: the variants and the Kconfig traps.
- `measurement-validity/code-placement`: the hot code in the CCM SRAM.
- `default-latencies/thread-to-thread/thread2thread-1m/experiment.md`: the two modes
  of the thread to thread latency.
- `wp3-kconfig-ranking.md` (project notes, not in this repository): the
  ranked list of the Kconfig factors.
