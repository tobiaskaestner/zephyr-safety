# kernel-latency

## Background

This is the top study of the latency study. The question of the study is
in `study.yaml`: how long does the Zephyr kernel delay the response to
an interrupt on a Cortex-M MCU, which kernel settings and loads change
the delay, and by how much? The study measures three latencies:

- M1, IRQ entry (`irq`): the time from the edge to the first
  instruction of the ISR.
- M2, ISR to thread (`isr2thr`): the time from the ISR to the first
  instruction of the thread that the ISR wakes.
- M3, thread to thread (`t2t`): the time from a wake call in one thread
  to the first instruction of the woken thread.

The board is not fixed at this level. The instances of the sub-studies
name the board. Each experiment is in the folder of the study that owns
it. Other studies refer to an experiment by its name, which is unique.

## Experiments

The study has no experiments of its own. Its five sub-studies give the
answer:

- `measurement-validity`: do the benchmark apps measure the latency of
  the kernel, and not an effect of the measurement method, the code
  layout or the host?
- `default-latencies`: the three latencies with the board and kernel
  defaults and an idle CPU. It gives the central results
  `irq-entry-p99-direct`, `isr2thr-p99-sem` and `t2t-p99-sem`.
- `load-scaling`: how the latencies grow with the number of threads and
  kernel timers, and which data structure and SysTick priority set the
  growth. It gives the central result `timer-slope`.
- `kconfig-factors`: which Kconfig options of the WP3 ranking change
  the three latencies, and by how much. It gives the central results
  `irq-ranking`, `wake-ranking` and `t2t-ranking`.
- `mask-time`: which call sites of the kernel mask the interrupts, for
  how long, and how the longest mask section grows with the load. It
  gives the central result `longest-by-load`.

## References

- `st-measurement-validity/study.md`: the checks of the method.
- `st-default-latencies/study.md`: the three latencies with the
  defaults.
- `st-load-scaling/study.md`: the growth with the load.
- `st-kconfig-factors/study.md`: the Kconfig factors.
- `st-mask-time/study.md`: the interrupt mask time.
- `doc/benchmark-guide/reference/files/study-yaml.rst` and
  `doc/benchmark-guide/reference/files/results-tree.rst`: the files of a
  study design and the results tree.
