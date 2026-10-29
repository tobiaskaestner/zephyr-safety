# stimulus-path

## Background

The edge sample of the study starts at the compare match of TIM2. The
latency thus contains a hardware path that the software of an
application does not see: the timer output, the pin, the wire, the input
synchronizer of the response pin and the EXTI line. The upstream
interrupt benchmark (Zephyr PR 117170) has no such path. It pends the
IRQ with a store to `NVIC->STIR` from a spinning thread.

The option `LATBENCH_SWTRIG` adds the same software trigger to
`irq_latency` and `wake_latency`, beside the edges, in the same image. The
same ISR takes both time stamps, so the difference of the two
histograms is free of the code placement effect. The method page of the
guide (software trigger) gives the bound of the offset of a software
sample.

The study asks three things:

1. How many cycles is the hardware path (H1)?
2. Which part of the distribution does a software trigger miss (H2)?
3. Why is the software-triggered wake about 470 cycles slower than the
   edge wake in the slow mode (H3), and does the software span agree
   with the upstream numbers (H4)?

For question 3, the code of the scheduler gives a mechanism. The wake
calls `z_time_slice_reset()` for the woken thread. It aborts the slice
timeout of the CPU. If the preempted thread is time-sliced, its slice
timeout is active, and in the slow mode it is the first timeout. Then
the abort reprograms SysTick, and the add of the new slice timeout
reprograms it again. The idle thread has no slice timeout. The upstream
benchmark does not see this cost, because its spinning thread is
cooperative.

## Experiments

- `irq-swtrig-1m`: the entry latency from the edge and from STIR in one
  image, for the paths `wrapped` and `direct`, with an idle and a busy
  CPU. It tests H1 and H2.
- `wake-swtrig-250k`: the wake latency from the edge and from STIR, with
  and without time slicing, from idle and from a busy thread, and with
  the configuration of the upstream benchmark. It tests H3 and H4.

## References

- Comparison of Zephyr PR 117170 with the study (agent notes,
  `pr-117170-comparison.md`), and the exploratory PR runs on the same
  board (`pr-117170/README.md`).
- Manual quick checks of 2026-10-29 and 2026-10-30 (run-log of the agent
  notes; not data).
- Zephyr `kernel/timeslicing.c` (`slice_reset()`), `kernel/timeout.c`
  (`z_try_abort_timeout()`), `kernel/sched.c` (`update_cache()`) at the
  tree `ws-up`.
