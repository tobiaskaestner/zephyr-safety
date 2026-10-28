# timeout-queue-cost

## Background

This study measures how a load changes the IRQ latency (`irq`, M1) and
the ISR to thread wake latency (`isr2thr`, M2). The question of the
study is in `study.yaml`: which load makes the wake slower, how much
does each periodic timer and each load thread add, and how does the
timeout queue backend change the latency with 256 periodic timers?

All experiments use the app `wake_latency`, with a semaphore given from
the wrapped ISR. The woken thread has priority 0. The board defaults
apply: `SCHED_SIMPLE`, time slicing on, and the timeout queue backend
DLIST. The SysTick ISR and the EXTI0 ISR (the stimulus) have the same
priority.

The study tests five kinds of load. The load generators are in the
latency plan, §2.4.

- Blocked threads: each load thread waits forever on a semaphore of its
  own (priority 5).
- Sleeper threads: each load thread sleeps 1..20 ms in a loop
  (priority 5). Each sleep adds a timeout and a thread switch.
- Busy threads: each load thread runs a busy loop at the lowest
  priority. With time slicing, the busy threads take turns at each slice
  expiry (20 ms).
- Periodic timers: N periodic `k_timer`s, period 10..100 ms, random
  start. Their expiry functions run in the SysTick ISR. Each restart
  inserts a timeout into the timeout queue.
- Far timers: 256 one-shot timers one hour away. They change only the
  length of the timeout queue.

The study uses these mechanisms:

1. The DLIST backend keeps the timeouts in the order of expiry. An
   insert walks only the timeouts that expire before the new one.
2. With time slicing, each wake resets the time slice, and the reset
   inserts a timeout. Without time slicing, the wake has no slice reset.
3. With `SCHED_SIMPLE`, the woken thread has the highest priority. Thus
   its insert into the ready queue does not walk the busy threads.

## Experiments

The study owns `wake-timeout-skiplist-1m`. It reads `wake-threads-1m`,
`wake-timers-1m` and `wake-timeout-backends-1m` with imports. The study
`zephyr-versions` owns these three experiments. All four experiments
run on the tree `ws-up`.

`wake-threads-1m` is the thread axis of the latency plan (§2.4). It
measures the number and the kind of load threads. The point `none-n0`
has no load threads. It is the reference, in the same binary as the
other points, apart from the load.

`wake-timers-1m` is the timer axis of the latency plan (§2.4). It
measures the number of kernel timers, with and without time slicing.
The point `t0` is the reference. The far timers show the cost of the
length of the timeout queue alone.

`wake-timeout-backends-1m` measures the timeout queue backends with 256
periodic load timers: DLIST, MINHEAP, WHEEL and BUCKET. The point
`dlist` gives a reference in the same binary as the other points. The
point `t256-default` of `wake-timers-1m` has the same load with the
DLIST backend. The SKIPLIST backend is not in all Zephyr versions. Thus
it is in a separate experiment, `wake-timeout-skiplist-1m`, with the same
axis name `backend`. Then `wake-timeout-backends-1m` can run on more than
one tree.

The predictions were written on 2026-10-24, before the runs
`wake-timers-1m/20261024T225125Z` and `wake-threads-1m/20261025T004141Z`
(dates from `hypotheses.yaml`):

- H1: a load makes the wake slower only through the timeouts in the
  timeout queue that expire before a new timeout. Blocked threads and
  far timers cost nothing. Busy threads at a lower priority do not make
  the insert into the ready queue longer. Sleeper threads make the
  `isr2thr` grow.
- H2: periodic timers cost in the timer ISR (restart) and in the slice
  reset of each wake. Thus with time slicing, the `isr2thr` grows with
  the number of timers.

`wake-timeout-backends-1m` and `wake-timeout-skiplist-1m` stated no prediction
before their runs. Their tail is the central result `backend-tail`. The
slopes per timer and per thread are the central results `timer-slope`
and `thread-slope`.

## References

- `hypotheses.yaml`: the hypotheses H1 and H2, and their checks.
- `st-zephyr-versions/ex-wake-threads-1m/experiment.md`: the thread
  axis.
- `st-zephyr-versions/ex-wake-timers-1m/experiment.md`: the timer axis.
- `st-zephyr-versions/ex-wake-timeout-backends-1m/experiment.md`: the
  backends and the DLIST reference.
- `ex-wake-timeout-skiplist-1m/experiment.md`: the SKIPLIST backend.
- Latency plan §2.4: the load generators.
- `st-load-scaling/st-systick-priority/study.md`: SysTick at a lower
  priority.
