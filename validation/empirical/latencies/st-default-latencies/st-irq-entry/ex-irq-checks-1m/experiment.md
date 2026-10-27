# irq-checks-1m

## What it measures

App `irq_latency`, metric `irq`: the IRQ entry latency of the direct
path. The points check the causes of its second mode and larger tail.

## Method

- Tree `ws-safety`, direct path, 1M samples per point, random stimulus
  interval 100..500 us.
- No cube: each point changes one factor against `direct-idle` of
  `irq-baseline-1m` (poll 100 ms, 170 MHz, idle CPU, time slicing on).
  `busy-noslice` changes two factors.
- Both clock overlays keep APB1 at /1. Thus TIM2 still runs at the core
  clock.

## Axes

- **poll**: the poll interval of the main thread (`LATBENCH_POLL_MS`):
  10 ms, 100 ms, 1000 ms. The main thread runs other code at each poll,
  thus more often at 10 ms and less often at 1000 ms. The axis tests the
  cache-miss cause of the second mode.
- **clock**: 170 MHz, 85 MHz or 16 MHz, set with a clock overlay. The
  clock driver sets the flash wait states for the new frequency. At
  16 MHz the flash has 0 wait states.
- **background**: `idle` or `busy` (`LATBENCH_BG_BUSY`). The busy CPU
  gives the larger tail.
- **slicing**: `slice` or `noslice` (`TIMESLICING: n`). The axis tests
  time slicing as the cause of the larger tail.
