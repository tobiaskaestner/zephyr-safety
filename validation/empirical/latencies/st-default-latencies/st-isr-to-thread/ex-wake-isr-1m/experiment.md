# wake-isr-1m

## Question

How long does it take from the ISR to the first instruction of the
thread that the ISR wakes (M2)? The experiment measures each kernel
object that an ISR can use to wake a thread, with the board defaults
and an idle CPU.

## Method

App `wake_latency`, tree `ws-safety`, board defaults, idle CPU. 1M
samples per point. The stimulus is the default of the app (random
interval 100..500 us).

The woken thread has priority 0. It is preemptible, and time slicing can
apply to it.

| Point | Settings | Why |
|---|---|---|
| `wrapped-sem` | ISR through `_isr_wrapper`, `k_sem_give` | The semaphore, from the default ISR kind. |
| `direct-sem` | direct ISR (`LATBENCH_WAKE_ISR_DIRECT`), `k_sem_give` | The compare of the two ISR kinds. |
| `wrapped-event` | `LATBENCH_WAKE_EVENT` | The event object. |
| `wrapped-msgq` | `LATBENCH_WAKE_MSGQ` | The message queue (4-byte message). |
| `wrapped-fifo` | `LATBENCH_WAKE_FIFO` | The FIFO. |
| `wrapped-poll` | `LATBENCH_WAKE_POLL` | The poll signal. |

The sem points come first. Thus a partial run still has the compare of
the two ISR kinds.

## References

- `../ex-wake-anchors-1m/experiment.md`: the settings that make the two modes.
- `st-measurement-validity/st-stimulus-sampling/ex-wake-phase-1m/experiment.md`: the tick phase of the two modes.
- `tests/benchmarks/wake_latency/Kconfig`: the ISR kinds and the kernel objects.
