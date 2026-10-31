.. _benchguide-central:

Central results
===============

A :term:`central result` is a sentence with measured values in it. It
is an entry of ``central_results`` in ``study.yaml``
(see :doc:`files/study-yaml`):

``id``
   The name of the result.

``statement``
   The sentence, with blanks (placeholders) for the values.

``from``
   The data: ``experiment`` (or a list), ``point`` (or a list), ``axes``,
   ``exclude`` (:term:`point` IDs), ``tree`` and ``metric`` (or a list). A
   ``conclusion`` has ``hypotheses`` instead. A result of a sub-study has
   ``substudy``.

``stat``
   What the build calculates from the data (see the table below).

``group_by``
   Only for an aggregate stat: the axes that divide the points into
   groups.

``unit``
   The unit of the values. The build copies it into ``study.json``.

The build calculates one or more rows from the data. A row is a set of
names with a value each. Then the build fills the statement once for
each row. Each filled statement is one sentence. Before it fills the
statement, the build joins its lines into one line.

``study.py analysis show --explain`` prints the definition, the rows and
the sentences (see :ref:`benchguide-explain-form`).
:doc:`../howto/write-a-central-result` gives the steps to write a
central result.

Placeholders
------------

A placeholder is a Python format field: ``{name}`` or ``{name:spec}``.
``name`` is a name of the row. ``spec`` is a Python format
specification:

- ``{p99:.0f}`` writes 41 for the value 41.0 (no decimals).
- ``{slope:.1f}`` writes 0.7 for the value 0.6791.
- ``{bound:.1e}`` writes 2.3e-06 for the value 0.00000231.
- ``{confidence:.0%}`` writes 95% for the value 0.95.

A name can have a dot or a hyphen, for example ``{p99.99}``. If the spec
does not fit the value (for example ``.0f`` for a text), the build writes
the value without the spec.

Each row has these names:

- ``board`` and ``instance``: the board and the :term:`instance` path of the
  instance that the build makes.
- ``run``: the :term:`run` ID, ``<experiment>/<UTC>``.
- ``tree``: the :term:`tree` of the point.
- ``metric``: the metric of the row, if ``from`` has one.
- For a per-point stat: ``point`` (the point ID) and one name for each
  axis of the point, with the value name (for example ``path``,
  ``background``).
- For an aggregate stat: only the axes of ``group_by``, not ``point``.
- The names that the stat gives (table below).

A few stats give rows without ``run`` and ``tree`` (see the table).

.. list-table:: Names that each stat adds to a row
   :header-rows: 1
   :widths: 30 70

   * - ``stat``
     - Names in the row
   * - a stat or a list of stats (``p99``, ``[p99, p99.99]``, ``max``,
       ``mode_share(1)``, ``drift_per_wake``)
     - One name for each stat, with the value of the point:
       ``{p99}``, ``{p99.99}``.
   * - ``value`` (with ``meta.<key>`` metrics)
     - ``<key>`` for each metric (the name without ``meta.``), and
       ``value``. The row has no ``metric``.
   * - ``top_site``
     - ``max_net``, ``place`` (the function of the mask site with the
       largest ``max_net``, with ``(via ...)`` for inlined functions) and
       ``ctx``.
   * - ``phase_share_range``
     - ``min`` and ``max``: the smallest and the largest share of a phase
       bin (1 is uniform).
   * - ``hist_identical_count``
     - ``hist_identical_count`` (the points of the re-run with the same
       histograms as the point of the owner :term:`study`) and ``n`` (the points
       with a point of the owner). One row, without ``run`` and ``tree``.
   * - ``{spread: [stats]}``
     - ``points`` (the points in the group), and for each stat its
       spread (max - min) / min over the group.
   * - ``{spread_abs: [stats]}``
     - ``points``, and for each stat max - min over the group.
   * - ``{slope: {stat, axis}}``
     - ``slope``, ``intercept`` and ``points``: the least-squares line of
       the stat over the ``value:`` numbers of the axis. A point whose axis
       value has no ``value:`` is not used. A group with fewer than two
       points gives no row.
   * - ``{fit_linear: {stat, x: [axes]}}``
     - As ``slope``. x is the sum of the ``value:`` numbers of the axes.
   * - ``{diff_rank: [stats]}``
     - ``stat``, ``first`` (the point with the largest change),
       ``first_diff`` (its change as an integer) and ``ranking`` (all
       points, ``<point> (+n)``). The change of a point is its value minus
       the value of the point with ``variant: baseline`` and the same
       other axes. One row for each metric, stat and series.
   * - ``{tree_diff: stat}``
     - ``tree_diff``: the value of ``ws-up`` minus the value of
       ``ws-safety``. One row for each point and metric, with ``point``,
       ``metric`` and the axes, without ``run`` and ``tree``.
   * - ``{ram_cost: [stats]}``
     - For each stat: the median over the points with a ``place`` value
       that starts with ``r``, minus the median over the points with a
       ``place`` value that starts with ``f``.
   * - ``{exceedance_bound: {thresholds: [..], confidence: c}}``
     - ``load_seed``, ``threshold``, ``count`` (the :term:`samples <Sample>` at or above the
       threshold), ``n``, ``bound`` (a one-sided Poisson upper bound of
       P(value >= threshold) per sample, rounded up to 3 digits) and
       ``confidence``. One row for each point, metric and threshold.
   * - ``conclusion``
     - No row (see below).

Rows of a per-point stat and of an aggregate stat
-------------------------------------------------

A series is the points of one run on one tree. A per-point stat (a stat
or a list of stats, ``value``, ``top_site``, ``phase_share_range``,
``exceedance_bound``) gives one row for each point, metric and series.

An aggregate stat (``spread``, ``spread_abs``, ``slope``, ``fit_linear``,
``ram_cost``) puts the points into groups and gives one row for each
group and metric. There is one group for each series and each
combination of values of the ``group_by`` axes. Without ``group_by``, a
group is one series.

The statement does not change the groups. In a group, each axis that is
not in ``group_by`` has several values. Thus the statement of an
aggregate can name only the axes of ``group_by``. The lint finds these
errors (see :ref:`benchguide-lint`):

- The statement names an axis that is not in ``group_by``.
- ``group_by`` is on a stat that is not an aggregate.
- ``group_by`` names an axis that the :term:`experiment` does not have.

Run and tree tag
----------------

If the rows come from more than one run and the statement does not name
``{run}``, each sentence ends with the UTC time of its run. If the rows
come from more than one tree and the statement does not name
``{tree}``, each sentence ends with its tree. The tag has the form
``[<run UTC>, <tree>]``, with only the parts that apply.

Missing values
--------------

If the data cannot give a value (no point for ``from``, a quantile in
the overflow bin, fewer than two points for a spread), the central
result has no sentence. It is ``not evaluated``, and ``not_evaluated``
in ``study.json`` gives the reason. An error of the tools gives ``not
evaluated`` with the reason ``tool error: ...``.

If a placeholder names a value that the row does not have, the build
keeps the placeholder in the sentence as it is. The name goes into the
list ``unfilled`` of the result. ``analysis show --explain`` prints this
list.

Conclusion and sub-study
------------------------

``stat: conclusion`` is a sentence without data. ``from`` names the
:term:`hypotheses <Hypothesis>` that the sentence is based on. The build does not fill
placeholders in a conclusion. The result has the :term:`verdict` of each
hypothesis (``verdicts_of_hypotheses``) and the verdict ``open (a person
confirms the sentence)``. A person sets the verdict ``confirmed`` or
``wrong``:

.. code-block:: console

   scripts/probatrix/benchmarks/study.py instance verdict <instance folder> --central-result <id> \
       --verdict confirmed --by "<name>"

``from: {substudy: <name>}`` shows the central result with the same
``id`` of the sub-study ``<name>``. The parent instance shows the
sentences, the rows and the verdict of the result of the child instance.
If the child has no result with this ``id``, the result is ``not
evaluated``.

.. _benchguide-central-examples:

Examples
--------

The examples are entries of the design of the suite. Each example gives
the entry of ``study.yaml`` and a sketch of the output of ``study.py
analysis show --explain``. The values in the sketches are examples, not
results of the study.

A per-point stat with two runs. The entry is in
``st-default-latencies/st-irq-entry/study.yaml``:

.. code-block:: yaml

   - id: irq-entry-p99-direct
     statement: >
       With the board defaults and an idle CPU, the IRQ entry latency of
       the direct path has a p99 of {p99:.0f} cycles.
     from: {experiment: irq-baseline-1m, point: direct-idle, tree: ws-up, metric: irq}
     stat: p99
     unit: CPU cycles (170 MHz)

.. code-block:: none

   == kernel-latency/st-default-latencies@nucleo_g474re/st-irq-entry [irq-entry-p99-direct]
      statement: With the board defaults and an idle CPU, the IRQ entry latency of the direct path has a p99 of {p99:.0f} cycles.
      from: {'experiment': 'irq-baseline-1m', 'point': 'direct-idle', 'tree': 'ws-up', 'metric': 'irq'}
      stat: p99
      row: run=irq-baseline-1m/<UTC 1>, tree=ws-up, point=direct-idle, path=direct, background=idle, metric=irq, p99=41
        -> With the board defaults and an idle CPU, the IRQ entry latency of the direct path has a p99 of 41 cycles. [<UTC 1>]
      row: run=irq-baseline-1m/<UTC 2>, tree=ws-up, point=direct-idle, path=direct, background=idle, metric=irq, p99=55
        -> With the board defaults and an idle CPU, the IRQ entry latency of the direct path has a p99 of 55 cycles. [<UTC 2>]

The instance has two evidence runs of ``irq-baseline-1m``, and the
statement does not name ``{run}``. Thus each sentence ends with the UTC
time of its run. ``from`` selects one tree, so the tag has no tree.

An aggregate stat with ``group_by``. The entry is in
``st-load-scaling/st-timeout-queue-cost/study.yaml``:

.. code-block:: yaml

   - id: thread-slope
     statement: >
       With {kind} load threads, the isr2thr p99 grows by {slope:.1f}
       cycles per thread ({tree}).
     from: {experiment: wake-threads-1m, metric: isr2thr}
     stat: {slope: {stat: p99, axis: threads}}
     group_by: [kind]
     unit: cycles per thread

.. code-block:: none

   == kernel-latency/st-load-scaling@nucleo_g474re/st-timeout-queue-cost [thread-slope]
      statement: With {kind} load threads, the isr2thr p99 grows by {slope:.1f} cycles per thread ({tree}).
      from: {'experiment': 'wake-threads-1m', 'metric': 'isr2thr'}
      stat: {'slope': {'stat': 'p99', 'axis': 'threads'}}
      group_by: ['kind']
      row: run=wake-threads-1m/<UTC>, tree=ws-up, metric=isr2thr, kind=blocked, slope=0.6791, intercept=1667, points=4
        -> With blocked load threads, the isr2thr p99 grows by 0.7 cycles per thread (ws-up).
      [...]

There is one row for each value of ``kind`` and each tree. The statement
names ``{tree}``, so the sentences have no tag. A group has the four
values of ``threads``. Thus ``{threads}`` in the statement is a lint
error.

A conclusion. The entry is in
``st-measurement-validity/st-clock-drift/study.yaml``:

.. code-block:: yaml

   - id: drift-cause
     statement: >
       Each SysTick reprogram loses about 8 cycles, and the gap
       compensation removes the drift. With many load timers, the driver
       also loses whole reloads when the shortest reload is too short.
     from: {hypotheses: [H1, H2]}
     stat: conclusion

.. code-block:: none

   == kernel-latency/st-measurement-validity@nucleo_g474re/st-clock-drift [drift-cause]
      statement: Each SysTick reprogram loses about 8 cycles, and the gap compensation removes the drift. With many load timers, the driver also loses whole reloads when the shortest reload is too short.
      from: {'hypotheses': ['H1', 'H2']}
      stat: conclusion
        -> Each SysTick reprogram loses about 8 cycles, and the gap compensation removes the drift. With many load timers, the driver also loses whole reloads when the shortest reload is too short.

A conclusion has no row. ``study.json`` has the verdict ``open (a person
confirms the sentence)`` and the verdicts of the hypotheses in
``verdicts_of_hypotheses``.
