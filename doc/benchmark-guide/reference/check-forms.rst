.. _benchguide-check-forms:

Check forms
===========

Metrics:

``irq``, ``isr2thr``, ``irq2thr``, ``t2t``, ...
   A latency histogram of the :term:`app`.
``meta.<key>``
   A ``LAT META`` value (stat ``value``). ``meta.m4_masked_share`` is
   ``m4_masked_cyc / m4_window_cyc``. ``meta.used`` and ``meta.dropped``
   come from the ``LAT M4 BEGIN`` line.
``m4.<kind>[.<ctx>][<function>]``
   The M4 sites of a kind (``mask``, ``isr``), of a context (``t`` thread,
   ``e<n>`` exception n: ``e14`` PendSV, ``e15`` SysTick, ``e22`` IRQ 6)
   and of a function. A site has the function that starts the mask
   section and its inlined functions. ``<function>`` matches one of them.
``tail.<hist>``
   The witness table of a histogram (``LATBENCH_TAIL``, see
   :doc:`../explanation/tail-witnesses`).
no metric
   The :term:`point` itself: ``drift_per_wake`` (``clock_drift_cyc / samples``),
   ``drift_ppm``.

Stats of a histogram:

- ``n``, ``min``, ``max``, ``mean``, ``invalid``.
- ``p<q>``, for example ``p50`` or ``p99.99``. The value is the lower
  edge of the bin that holds the quantile. Thus in a coarse bin of width
  w, the true value can be up to w - 1 higher.
- ``count_ge(x)``: the :term:`samples <Sample>` at or above x. x must be a bin edge.
- ``mode_share(k)``: the share of the samples in mode k, or 0 if there
  is no mode k.
- ``max(<stat>)`` and ``min(<stat>)``: the largest and the smallest value
  of the stat over the selected points.

A mode is a group of fine bins. Each bin of the group holds at least
0.1 % of the samples. Two neighbour bins of a group are at most 2 cycles
apart. The modes have numbers in the order of their values: mode 1 is
the fastest.

Stats of a witness table: ``n`` (rows), ``seen`` (samples at or above
``LATBENCH_TAIL_MIN_CYC``), ``exc_min``, ``rows_ge(x)`` (rows of x cycles or
more), ``explained_share(x)`` (the share of these rows with a cause other
than ``none``), ``cause_share(c, x)`` and ``label_share(l, x)`` (the share
of these rows with the cause c or the label l). If no row has x cycles or
more, the check is not evaluated.

Stats of M4 sites: ``n`` (sum of the sections), ``max``, ``max_net``,
``min_net`` (net: minus the floor of the calibration), ``max(<x>)`` over
the sites, ``top_place`` (the function of the site with the largest
``max_net``).

``select``: ``{point: id | [ids]}``, ``{axes: {axis: value | [values]}}``
or ``{axis: value | [values]}``. A point that ``select`` names must be in
the data. An M4 metric with ``[function]`` must find that function in
some point of the :term:`experiment` (else the name has a typo, or the build has
other code).

``expect`` has exactly one form (``ratio_to`` with ``range``, ``within``
with ``tolerance_bins``):

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Form
     - Confirmed if
   * - ``range: [lo, hi]``
     - each value is in lo..hi (``null``: no limit). A quantile in a coarse
       bin is in the range only if the whole bin is. If a limit is inside
       the bin, the check is not evaluated
   * - ``equals: x``
     - each value is x (``top_place``: x is the start function or one of
       its inlined functions)
   * - ``spread_le: x``
     - (max - min) / min over the selected points <= x (two points or
       more, all values above 0)
   * - ``spread_abs_le: x``
     - max - min over the selected points <= x (two points or more)
   * - ``order: [p1, p2, ...]``
     - the values increase in this order of points. Each point must be
       there. Equal values are wrong.
   * - ``order: {axis: [v1, v2, ...]}``
     - the values increase along these axis values, for each value of the
       other axes
   * - ``diff_to: {REF, range}``
     - value - the value of the reference is in the range
   * - ``diff_to: {REF, spread_abs_le: x}``
     - the differences (value - reference) over the selected points
       differ by x or less (two points or more)
   * - ``ratio_to: {REF, stat}`` + ``range``
     - value / the value of the reference is in the range
   * - ``diff_change: {point: P, of: [Q, R], range}``
     - (value - P) - (Q - R), in the same run and :term:`tree`
   * - ``within: {experiment: E, stat: range}`` + ``tolerance_bins: k``
     - the value is in min..max of all points of E, +- k coarse bins
   * - ``hist_identical_to: {run | experiment, point}``
     - the histograms are the same, bin for bin (on the same tree, or on
       ``tree``). With ``experiment: E``, the reference is the point of the
       one evidence run of E

REF is ``point: P``, ``axes: {axis: v}`` (the point with this axis value
and the same other axes), ``run: <study path>/<experiment>/<UTC>`` with
``point``, ``points: {selected: reference}``, ``tree`` and
``revision: different`` (no verdict while the selected run and the
reference run have the same safety revision),
``experiment: E`` with ``point: same`` (the default), ``point: P`` and
``tree`` (E must have one evidence run with that point), or ``metric: M,
stat: S`` (the same point). The study must own or import E.

Use ``experiment:`` when the reference is the current data of another
experiment: the check then needs no change after a new campaign. Use
``run:`` only when the reference must stay one fixed run, for example the
old data that a new revision must reproduce. For ``max(<stat>)`` over the
points, the reference is that of the point that gives the max. A
``run:`` reference must not be excluded. The points of each run and tree
form a series. A check is confirmed only if it holds in each series, for
each metric and each stat.

A check that the data cannot give (no point, a quantile in the overflow
bin, a limit inside a coarse bin) is ``not evaluated``, with the reason.
An error of the tools gives ``tool error``. A check that has a ``TODO``
text, or whose :term:`hypothesis` statement has one, is ``draft``: the build does
not evaluate it. None of the three is confirmed or wrong. The hypothesis
stays open. A :term:`study` with a ``mode: rerun`` import
reads only its own runs of that experiment, never those of the owner.
