# wake-isr-1m

## What it measures

App `wake_latency`, metric `isr2thr`: the ISR to thread wake latency
(M2) for each kernel object that an ISR can use to wake a thread, with
the board defaults and an idle CPU.

## Method

- Tree `ws-up`, board defaults, idle CPU.
- 1M samples per point. The stimulus is the default of the app (random
  interval 100..500 us).
- The woken thread has priority 0. It is preemptible, and time slicing
  can apply to it.
- No cube: six explicit points. The sem points come first. Thus a
  partial run still has the compare of the two ISR kinds.

## Axes

- **isr**: the ISR kind. `wrapped` is an ISR through `_isr_wrapper`.
  `direct` is a direct ISR (`LATBENCH_WAKE_ISR_DIRECT`, point
  `direct-sem` only). The two sem points compare the two kinds.
- **primitive**: the kernel object of the wake. `sem` is `k_sem_give`.
  `event` (`LATBENCH_WAKE_EVENT`) is the event object. `msgq`
  (`LATBENCH_WAKE_MSGQ`) is the message queue, with a 4-byte message.
  `fifo` (`LATBENCH_WAKE_FIFO`) is the FIFO. `poll`
  (`LATBENCH_WAKE_POLL`) is the poll signal.
