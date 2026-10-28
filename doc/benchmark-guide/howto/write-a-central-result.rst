Write a central result
======================

:ref:`benchguide-central` gives the fields of a central result.

Examples
--------

Each example gives the entry of ``study.yaml``, the rows of the build,
and the sentences. The rows and the sentences are the output of ``study.py
analysis show --explain`` on the results tree of the study (state of
2026-10-27).

A per-point stat with two runs. The entry is in
``st-default-latencies/st-irq-entry/study.yaml``:

.. code-block:: none

   - id: irq-entry-p99-direct
     statement: >
       With the board defaults and an idle CPU, the IRQ entry latency of
       the direct path has a p99 of {p99:.0f} cycles.
     from: {experiment: irq-baseline-1m, point: direct-idle, tree: ws-up, metric: irq}
     stat: p99
     unit: CPU cycles (170 MHz)

   rows (one for each point, metric and series):
     run=irq-baseline-1m/20261024T155016Z, tree=ws-up, point=direct-idle,
       path=direct, background=idle, metric=irq, p99=41
     run=irq-baseline-1m/20261026T223523Z, tree=ws-up, point=direct-idle,
       path=direct, background=idle, metric=irq, p99=55

   sentences:
     With the board defaults and an idle CPU, the IRQ entry latency of the
     direct path has a p99 of 41 cycles. [20261024T155016Z]
     With the board defaults and an idle CPU, the IRQ entry latency of the
     direct path has a p99 of 55 cycles. [20261026T223523Z]

The instance has two evidence runs of ``irq-baseline-1m``, and the
statement does not name ``{run}``. Thus each sentence ends with the UTC
time of its run. ``from`` selects one tree, so the tag has no tree.

An aggregate stat with ``group_by``. The entry is in
``st-load-scaling/st-timeout-queue-cost/study.yaml``:

.. code-block:: none

   - id: thread-slope
     statement: >
       With {kind} load threads, the isr2thr p99 grows by {slope:.1f}
       cycles per thread ({tree}).
     from: {experiment: wake-threads-1m, metric: isr2thr}
     stat: {slope: {stat: p99, axis: threads}}
     group_by: [kind]
     unit: cycles per thread

   rows (one for each series, value of kind and metric, 2 of 6):
     run=wake-threads-1m/20261025T004141Z, tree=ws-safety, metric=isr2thr,
       kind=blocked, slope=0.6791, intercept=1667, points=4
     run=wake-threads-1m/20261025T004141Z, tree=ws-safety, metric=isr2thr,
       kind=busy, slope=1.663, intercept=2067, points=4

   sentences:
     With blocked load threads, the isr2thr p99 grows by 0.7 cycles per
     thread (ws-safety).
     With busy load threads, the isr2thr p99 grows by 1.7 cycles per
     thread (ws-safety).

The other four rows are for ``kind=sleeper`` and for the tree ``ws-up``.
The statement names ``{tree}``, so the sentences have no tag. A group has
the four values of ``threads``. Thus ``{threads}`` in the statement is a
lint error.

A conclusion. The entry is in
``st-measurement-validity/st-clock-drift/study.yaml``:

.. code-block:: none

   - id: drift-cause
     statement: >
       Each SysTick reprogram loses about 8 cycles, and the gap
       compensation removes the drift. With many load timers, the driver
       also loses whole reloads when the shortest reload is too short.
     from: {hypotheses: [H1, H2]}
     stat: conclusion

   rows: none

   sentence:
     Each SysTick reprogram loses about 8 cycles, and the gap compensation
     removes the drift. With many load timers, the driver also loses whole
     reloads when the shortest reload is too short.

   study.json: verdict "open (a person confirms the sentence)",
     verdicts_of_hypotheses {H1: open, H2: open}
