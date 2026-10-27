# load-scaling

## Background

This study measures how the latencies grow with the number of threads
and kernel timers. It also asks which kernel data structure (the ready
queue, the timeout queue backend) and which SysTick priority set the
growth. The question of the study is in `study.yaml`. The study has no
experiments and no hypotheses of its own. Its three sub-studies own the
experiments and the hypotheses.

## Experiments

- `timeout-queue-cost`: which load makes the ISR to thread wake slower,
  how much each periodic timer and each load thread adds, and how the
  timeout queue backend changes the latency with 256 periodic timers. It
  gives the central results `timer-slope`, `thread-slope` and
  `backend-tail`.
- `systick-priority`: how much of the IRQ tail under timer load comes
  from the SysTick ISR at the same priority as the device IRQ, and if a
  lower SysTick priority makes the tail smaller. It gives the central
  result `systick-prio-tail`.
- `t2t-under-load`: how the thread to thread wake grows with periodic
  load timers and sleeper threads, and if its p50 follows the number of
  timeouts that expire before the slice deadline. It gives the central
  result `t2t-grows-with-n`.

## References

- `st-timeout-queue-cost/study.md`: the load kinds and the timeout queue
  backends.
- `st-systick-priority/study.md`: the SysTick priority.
- `st-t2t-under-load/study.md`: the thread to thread wake under load.
