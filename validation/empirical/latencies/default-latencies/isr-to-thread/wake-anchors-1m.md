# wake-anchors-1m

## Question

Which setting makes the two modes of the ISR to thread wake latency
(M2)?

`wake-isr-1m` showed the same two modes for all five kernel objects:
310 cycles apart, with 80 % and 20 % of the samples. Thus the cost is
in the common path of the wake and of the thread switch. The anchors of
this experiment find the setting that makes it.

## Method

App `wake_latency`, semaphore given from the wrapped ISR, trees
`ws-safety` and `ws-up`. 1M samples per point. One kernel object is
sufficient, because all five objects have the same two modes.

The points are the cube `anchor` x `arch`. The axis `anchor` has the
values `default`, `noslice` and `lean`. The axis `arch` has the values
`legacy` (PendSV) and `switch` (`USE_SWITCH=y`).

| Point | Settings | Why |
|---|---|---|
| `default-legacy` | board and kernel defaults | The reference. |
| `default-switch` | `common/conf/use_switch.conf` | The new arch interface. |
| `noslice-legacy` | `TIMESLICING: n` | Only time slicing off. |
| `noslice-switch` | `TIMESLICING: n`, `use_switch.conf` | As `noslice-legacy`, with the new arch interface. |
| `lean-legacy` | `common/conf/lean.conf` | No time slicing, no stack guard, `-O2`. |
| `lean-switch` | `lean.conf`, `use_switch.conf` | As `lean-legacy`, with the new arch interface. |

## References

- `wake-isr-1m.md`: the two modes for the five kernel objects.
- `tests/benchmarks/common/conf/lean.conf`, `use_switch.conf`: the anchor settings.
