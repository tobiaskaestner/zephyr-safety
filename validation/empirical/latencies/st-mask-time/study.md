# mask-time

## Background

This study measures which call sites of the kernel mask the interrupts,
and for how long. It also measures how the longest mask section grows
with the load. The question of the study is in `study.yaml`.

The study uses the M4 method (`doc/benchmark-guide/m4.rst`). The tree
`ws-up-irqoff` has the hooks `CONFIG_ARM_IRQ_MASK_HOOKS` and
`CONFIG_ARM_IRQ_MASK_HOOKS_ISR`. The hooks record each mask section and
each ISR body. The latency histograms of these runs are not data
(`LAT META m4=1`). The analysis uses the M4 tables
(`scripts/benchmarks/m4.py`) only. All values are in cycles at 170 MHz.
`st-measurement-validity/st-mask-instrumentation` checks the method.

The study uses these mechanisms:

1. The walk. The DLIST insert walks over each timeout that expires
   before the new one, with the timeout lock held. The walk costs about
   25 cycles for each timeout. The WHEEL backend has no insert walk
   over the queue (review-2026-10-25, §4, finding 8).
2. The site `z_add_timeout()`. Its lock is inlined there, so all callers
   share one site. The context splits the callers:
   - SysTick (`e15`): the timer restarts and the sleeper wakes.
   - irq6, the EXTI0 ISR (`e22`): the slice reset in the give.
   - thread (`t`): the slice reset at a switch, and `k_sleep()`.
3. The sources of timeouts. Each restart of a periodic timer walks the
   queue. The sleeper wakes run in the SysTick ISR. The slice reset adds
   a timeout in the EXTI0 ISR and at a switch.
4. The SysTick ISR body. It contains the callbacks and the restarts of
   several expiries in one tick. At the same priority, EXTI0 waits for
   the whole body.
5. Sites with a fixed cost: the middle part of PendSV, the wake window
   of `arch_cpu_idle`, `k_sem_give` and `k_sem_take`.

## Experiments

`m4-sweep` measures the mask time and the ISR body time of each site
over three loads: periodic load timers, sleeper threads and time
slicing. The app is `wake_latency`. The board time is about 40 min:
24 points x (30 s + 200000 x 300 us = 60 s + 10 s).

`m4-thread` measures the mask sites that a thread to thread wake adds,
for a semaphore and for a mutex. The app is `thread_latency`. The giver
is a thread, so its wake call and the switch to the taker run in thread
context. The mutex does the priority inheritance under the lock. The
points with 64 load timers compare the timeout walk in the thread app
with `m4-sweep` and `m4-validate`. The board time is about 4 min:
4 points x (30 s + 200000 x 100 us = 20 s + 10 s).

The study imports `m4-validate` from
`measurement-validity/mask-instrumentation`. Its points `t64-same` and
`t256-same` give values at 64 and 256 timers in `wake_latency`.

The predictions were written on 2026-10-25, before the runs
`m4-validate/20261025T235532Z`, `m4-sweep/20261026T000640Z` and
`m4-thread/20261026T004002Z` (dates from `hypotheses.yaml`):

- H1: the DLIST insert walk in `z_add_timeout` is the longest mask
  section. It grows about linearly with the timeouts in the queue,
  about 300 + 25 cycles for each timeout that it walks. The WHEEL
  backend removes it.
- H2: time slicing adds the EXTI0 and the thread entries of
  `z_add_timeout` (the slice reset). The restart walk in the SysTick ISR
  does not depend on slicing.
- H3: at the same priority, the SysTick ISR body is the largest
  blocking time for EXTI0. Its max grows faster with the timers than the
  longest mask section.
- H4: code that walks no list masks the interrupts only for a short
  time, and the load does not change this time. This applies to the
  sites with a fixed cost and to the thread to thread wake with a
  semaphore or a mutex.

The comment of `m4-sweep` said that the masked share "grows with the
load", with no limit. Thus the masked share is the central result
`masked-share`, not a hypothesis. The pairing counters and the dropped
sites of the M4 logs are acceptance checks in the `experiment.yaml`
files.

## References

- `hypotheses.yaml`: the hypotheses H1 to H4, and their checks.
- `ex-m4-sweep/experiment.md`: the load sweep in `wake_latency`.
- `ex-m4-thread/experiment.md`: the thread to thread wake.
- `doc/benchmark-guide/m4.rst`: the M4 method and the site names.
- `st-measurement-validity/st-mask-instrumentation/ex-m4-validate/experiment.md`:
  the check of the method, and the points `t64-same` and `t256-same`.
- `st-load-scaling/st-timeout-queue-cost/ex-wake-timers-1m/experiment.md`:
  the `ws-up` IRQ max at 256 timers.
- `st-default-latencies/st-thread-to-thread/ex-thread2thread-1m/experiment.md`:
  the same thread app without hooks.
- `claude/latency-benchmarks/m4-design.md` §5.2 (`m4-sweep`) and §5.3
  (`m4-thread`), outside this repository.
