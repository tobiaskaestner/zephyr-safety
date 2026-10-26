# fast-mode

## Question

Does the fast mode depend on the stimulus delay, or on other state?

The notes `later.md` (item L15) give these facts. With time slicing,
about 20 % of the wakes are faster: 300 cycles in M2 (ISR to thread),
700 cycles in M3 (thread to thread). The share is 20..21 % for all
kernel objects, both trees and both stimulus ranges (100..500 us in M2,
50..150 us in M3). The mean per tick phase is flat. Without time
slicing, there is no fast mode.

## Method

App `wake_latency`, semaphore given from the wrapped ISR, tree
`ws-safety`. 200000 samples per point.

| Point | Settings | Why |
|---|---|---|
| `r100-500` | random interval 100..500 us (the default range) | The baseline. |
| `r100-200` | random interval 100..200 us | A different range. |
| `r400-500` | random interval 400..500 us | A different range. |
| `fixed300` | fixed period 300 us, plus 1 cycle per edge | A fixed delay. |
| `poll1000` | default range, the main thread polls every 1000 ms (not 100 ms) | Other state in the main thread. |

How to read the result: if the share of the fast mode follows the range
(for example 0 % or 100 % with a fixed period), the cause depends on the
delay. If the share stays at 20 %, the cause is other state.

## References

- `later.md`, item L15 (latency notes): the fast mode.
- `../wake-isr-1m/experiment.md`, `../wake-anchors-1m/experiment.md`: the two modes in M2.
- `default-latencies/thread-to-thread/thread2thread-1m/experiment.md`: the two modes in M3.
