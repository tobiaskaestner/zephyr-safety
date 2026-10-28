# tick-mode

## Background

This study measures how the tickless kernel and the tick rate change the
three latencies. The question of the study is in `study.yaml`. It also
asks two more questions. Does the SysTick reprogram of the slice reset
make the two modes of the wake and the clock drift? How does the tick
rate set the share and the max of the IRQ tail? This study is the one
home of the mechanism of the two modes (H1 in `hypotheses.yaml`).

The defaults of the apps have the tickless kernel with 10000 ticks/s.
The study tests these variants:

- `ticks1000`: 1000 ticks/s. The kernel stays tickless, with the same
  slice and the same SysTick reprogram. The kernel rounds each timeout
  up to a 1 ms tick (170000 cycles).
- `tickless-off`: a periodic tick at 10000 ticks/s. A SysTick ISR comes
  every 17000 cycles (100 us), also when no timer expires.
- `tickless-off-100`: a periodic tick at 100 ticks/s, the Zephyr
  default without the tickless kernel. A SysTick ISR comes every 1.7M
  cycles (10 ms).

The study uses these mechanisms:

1. The SysTick reprogram. In the tickless kernel, the slice reset of a
   wake reprograms the SysTick. Without `TICKLESS_KERNEL`,
   `sys_clock_set_timeout()` returns at once (ws-up
   `drivers/timer/system_timer_generic.h:650`). Thus the slice reset
   never reprograms the SysTick, and the kernel resets no SysTick
   reload.
2. The slice walk. The slice reset also walks the timeout list. This
   walk stays without the tickless kernel.
3. The tick ISR. Without the tickless kernel, a SysTick ISR comes at
   each tick. At a lower tick rate, the kernel puts the expiries of the
   timers into fewer, longer tick ISRs.

## Experiments

This study owns no experiment. It imports `irq-kconfig-1m`, `wake-kconfig-1m`
and `thread-kconfig-1m` from the parent study `kconfig-factors`. The checks
compare a point with `baseline`, or with `baseline-t64`, of the same
run. The points with 64 load timers (`t64`) are in `irq-kconfig-1m` and
`wake-kconfig-1m`.

The predictions were written on 2026-10-25, before the runs
`wp3-t2t-1m/20261025T203235Z`, `wp3-wake-1m/20261025T205806Z` and
`wp3-irq-1m/20261025T223624Z` (dates from `hypotheses.yaml`):

- H1: the SysTick reprograms make the slow mode of the wake and of the
  thread to thread latency, and the clock drift. The baseline has the
  same two modes as `thread-baseline-1m`: about 20 % fast and 80 % slow.
  In `t2t` the slow mode is about 640 cycles slower (two SysTick
  reprograms). Without the tickless kernel, the latency has one mode
  (the fast mode), and the drift is about 0 ppm. With 64 load timers,
  the slice walk over about 30 timeouts adds 600..700 cycles.
- H2: the SysTick ISRs make the IRQ tail, and the tick rate trades the
  share of the tail against its max. At 10000 ticks/s without the
  tickless kernel, about 1..3 % of the edges wait for up to one SysTick
  ISR. The p99 increases from about 81 cycles (an earlier run) to some
  hundred cycles. With 64 timers at 100 ticks/s, each tick ISR handles
  about 16 expiries, and the max is 10000..20000 cycles.
- H3: with no load, 1000 ticks/s changes nothing. The p50 of `irq`,
  `isr2thr` and `t2t` and the drift for each reprogram stay the same.

The central result `tick-reprogram-modes` in `study.yaml` comes from H1.

## References

- `hypotheses.yaml`: the hypotheses H1, H2 and H3, and their checks.
- `../wp3-variants.md`: the variants and the Kconfig trap of
  `tickless-off`.
- `../study.md`: the three experiments.
- `st-default-latencies/st-thread-to-thread/study.md`: the two modes of
  `thread-baseline-1m`.
- `st-measurement-validity/st-clock-drift/study.md`: the clock drift.
- `drivers/timer/system_timer_generic.h` (ws-up tree):
  `sys_clock_set_timeout()`.
