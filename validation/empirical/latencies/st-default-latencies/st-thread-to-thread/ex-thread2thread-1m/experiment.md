# thread2thread-1m

## Question

How long does it take from a wake call in one thread to the first
instruction of the woken thread (M3)? The experiment measures each
kernel object, with the board and kernel defaults, on both trees.

## Method

App `thread_latency`, trees `ws-safety` and `ws-up`. 1M samples per
point. Random stimulus interval 50..150 us. Histograms with 2048 fine
and 2048 coarse bins.

The ISR wakes the giver thread (priority 2) at a random time. The giver
wakes the taker through the kernel object. `t2t` is the time from the
wake call to the taker.

| Point | Settings | Why |
|---|---|---|
| `sem` .. `wakeup` (11 points) | axis `primitive`, `LATBENCH_T2T_<OBJECT>`. The taker has priority 1 and preempts the giver. | One point for each kernel object. |
| `sem-nopreempt` | `LATBENCH_T2T_SEM`, `LATBENCH_T2T_PREEMPT: n` | The taker has priority 3: no preemption. |
| `mutex-nopreempt` | `LATBENCH_T2T_MUTEX`, `LATBENCH_T2T_PREEMPT: n` | As `sem-nopreempt`, for the mutex. |

The stimulus comes every 50..150 us, not every 100..500 us as in the M2
experiments. This keeps the board time short. All points of this
experiment use the same stimulus, so they compare with each other. The
share of the samples that meet the timer ISR is about 3 times larger
than in the M2 experiments.

Board time: about 1 h for the points of both trees.

## References

- `../ex-thread2thread-switch/experiment.md`: the same measurement with `USE_SWITCH=y`.
- `tests/benchmarks/thread_latency/Kconfig`: the kernel objects and `LATBENCH_T2T_PREEMPT`.
