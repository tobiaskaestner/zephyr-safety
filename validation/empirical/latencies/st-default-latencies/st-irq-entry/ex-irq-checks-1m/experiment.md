# irq-checks-1m

## Question

Where do the second mode and the larger tail of the direct path come
from?

`irq-smoke` showed a second mode, 20 cycles above the first mode, with
1.2 % of the samples. With a busy CPU, the tail was larger. This
experiment checks two hypotheses for these two observations
(hypotheses.yaml):

1. Flash or ART cache misses after other code ran make the second mode.
2. Time slicing makes the larger tail with a busy CPU.

## Method

App `irq_latency`, direct path, tree `ws-safety`. 1M samples per point.
Random stimulus interval 100..500 us.

The reference point is `direct-idle` of `irq-baseline-1m`. It has the
same settings: poll 100 ms, 170 MHz, idle CPU, time slicing on. Each
point changes one factor against the reference. `busy-noslice` changes
two factors.

| Point | Settings | Why |
|---|---|---|
| `idle-poll10` | `LATBENCH_POLL_MS: 10` | The main thread runs other code more often. If cache misses make the second mode, the share of the mode follows the poll rate. |
| `idle-poll1000` | `LATBENCH_POLL_MS: 1000` | The main thread runs other code less often. |
| `idle-85mhz` | 85 MHz clock overlay | A clock between 170 MHz and 16 MHz. The clock driver sets the flash wait states for the new frequency. |
| `idle-16mhz` | 16 MHz clock overlay | The flash has 0 wait states at 16 MHz. If cache misses make the second mode, the mode is not there. |
| `busy` | `LATBENCH_BG_BUSY` | The larger tail with a busy CPU. |
| `busy-noslice` | `LATBENCH_BG_BUSY`, `TIMESLICING: n` | The busy thread is preemptible, so it has a slice timeout. If time slicing makes the tail, the tail goes back to the idle level. |

Both clock overlays keep APB1 at /1, so TIM2 still runs at the core
clock.

## References

- `../ex-irq-smoke/experiment.md`: the second mode and the larger tail.
- `../ex-irq-baseline-1m/experiment.md`: the reference point `direct-idle`.
- `tests/benchmarks/common/boards/nucleo_g474re/clocks/`: the clock overlays.
