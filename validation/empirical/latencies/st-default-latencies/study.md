# default-latencies

## Background

This study measures the three latencies of the kernel with the board and
kernel defaults and an idle CPU:

- M1, IRQ entry: the time from the edge to the first instruction of the
  ISR.
- M2, ISR to thread: the time from the ISR to the first instruction of
  the thread that the ISR wakes.
- M3, thread to thread: the time from a wake call in one thread to the
  first instruction of the woken thread.

The question of the study is in `study.yaml`. The study has no
experiments of its own. Its three sub-studies give the answer.

## Experiments

- `irq-entry`: M1 for each interrupt path, and where its modes come
  from. It gives the central result `irq-entry-p99-direct`.
- `isr-to-thread`: M2 for each kernel object, and which setting makes
  its two modes. It gives the central result `isr2thr-p99-sem`.
- `thread-to-thread`: M3 for each kernel object, with the legacy and the
  new (`USE_SWITCH=y`) context switch. It gives the central result
  `t2t-p99-sem`.

## References

- `st-irq-entry/study.md`: the IRQ entry latency (M1).
- `st-isr-to-thread/study.md`: the ISR to thread latency (M2).
- `st-thread-to-thread/study.md`: the thread to thread latency (M3).
