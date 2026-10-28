.. _benchguide-central:

Central results
===============

A central result is characterisation: measured values in a sentence. It
is an entry of ``central_results`` in ``study.yaml``:

``id``
   The name of the result.

``statement``
   The sentence, with blanks (placeholders) for the values.

``from``
   The data: ``experiment`` (or a list), ``point`` (or a list), ``axes``,
   ``exclude`` (point IDs), ``tree`` and ``metric`` (or a list). A
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

``study.py analysis show ROOT --explain [ID ...]`` prints, for each central result
(or for the given IDs) of each instance below ``ROOT``: the definition,
each row, and the sentence of each row.

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

- ``board`` and ``instance``: the board and the instance path of the
  instance that the build makes.
- ``run``: the run ID, ``<experiment>/<UTC>``.
- ``tree``: the tree of the point.
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
       histograms as the point of the owner study) and ``n`` (the points
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
     - ``load_seed``, ``threshold``, ``count`` (the samples at or above the
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
- ``group_by`` names an axis that the experiment does not have.

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
list ``unfilled`` of the result. ``analysis show --explain`` prints this list.

Conclusion and sub-study
------------------------

``stat: conclusion`` is a sentence without data. ``from`` names the
hypotheses that the sentence is based on. The build does not fill
placeholders in a conclusion. The result has the verdict of each
hypothesis (``verdicts_of_hypotheses``) and the verdict ``open (a person
confirms the sentence)``. A person sets the verdict ``confirmed`` or
``wrong``:

.. code-block:: console

   scripts/benchmarks/study.py instance verdict <instance folder> --central-result <id> \
       --verdict confirmed --by "<name>"

``from: {substudy: <name>}`` shows the central result with the same
``id`` of the sub-study ``<name>``. The parent instance shows the
sentences, the rows and the verdict of the result of the child instance.
If the child has no result with this ``id``, the result is ``not
evaluated``.
