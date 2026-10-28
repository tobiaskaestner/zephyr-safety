# isr-to-thread

## Background

This study measures the ISR to thread wake latency (M2). The latency is
the time from the ISR to the first instruction of the thread that the
ISR wakes. All experiments use the app `wake_latency`. The woken thread
has priority 0. It is preemptible, and time slicing can apply to it.

The question of the study is in `study.yaml`: how long is the latency
for each kernel object, and which setting makes the two modes? The study
measures the five kernel objects that an ISR can use to wake a thread:

- the semaphore (`k_sem_give`)
- the event object
- the message queue, with a 4-byte message
- the FIFO
- the poll signal

An ISR is of one of two kinds. A `wrapped` ISR runs through
`_isr_wrapper`. This is the default kind. A `direct` ISR is a direct
ISR (`LATBENCH_WAKE_ISR_DIRECT`).

`wake-isr-1m` showed the same two modes for all five kernel objects. The
modes are 310 cycles apart, with 80 % and 20 % of the samples. Thus the
cost is in the common path of the wake and of the thread switch, not in
the kernel object.

The notes `later.md` (item L15) give these facts about the fast mode.
With time slicing, about 20 % of the wakes are faster: 300 cycles in M2,
700 cycles in M3 (thread to thread). The share is 20..21 % for all
kernel objects, both trees and both stimulus ranges (100..500 us in M2,
50..150 us in M3). The mean per tick phase is flat. Without time
slicing, there is no fast mode.

## Experiments

`wake-isr-1m` measures M2 for each kernel object, with the board
defaults and an idle CPU. It has 1M samples per point. The stimulus is
the default of the app, a random interval of 100..500 us. The semaphore
is measured from both ISR kinds, for the compare of the two kinds. The
other objects are measured from the wrapped ISR. The central result
`isr2thr-p99-sem` in `study.yaml` comes from the point `wrapped-sem`.

`wake-anchors-1m` finds the setting that makes the two modes. It uses
only the semaphore, because all five objects have the same two modes. It
runs on two trees, `ws-safety` and `ws-up`. The anchors are the
defaults, no time slicing, and `lean.conf` (no time slicing, no stack
guard, `-O2`). Each anchor runs with the legacy thread switch (PendSV)
and with the new arch interface (`USE_SWITCH=y`).

`wake-fast-mode` asks: does the fast mode depend on the stimulus delay, or on
other state? Each point changes the stimulus or the poll interval of the
main thread. The result has two readings:

- If the share of the fast mode follows the range (for example 0 % or
  100 % with a fixed period), the cause depends on the delay.
- If the share stays at 20 %, the cause is other state.

The study has no `hypotheses.yaml`. The experiment files give no
prediction.

## References

- `ex-wake-isr-1m/experiment.md`: the five kernel objects and the two
  ISR kinds.
- `ex-wake-anchors-1m/experiment.md`: the settings that make the two
  modes.
- `ex-fast-mode/experiment.md`: the stimulus delay and the poll interval.
- `later.md`, item L15 (latency notes): the fast mode.
- `st-default-latencies/st-thread-to-thread/study.md`: the two modes in
  M3.
- `st-measurement-validity/st-stimulus-sampling/ex-wake-phase-1m/experiment.md`:
  the tick phase of the two modes.
- `tests/benchmarks/wake_latency/Kconfig`: the ISR kinds and the kernel
  objects.
- `tests/benchmarks/common/conf/lean.conf`, `use_switch.conf`: the anchor
  settings.
