Skipped Results
###############

Every skipped test result carries a ``skip_class`` (set by zdocs from the
twister run), and every result a ``depends_met``: whether the build that
produced it met its test case's Kconfig ``depends_on``, read from that build's
``.config``.

``config``
   ztest skipped the test, and its ``depends_on`` is false in the build. The
   specification explains the skip.
``platform``
   The board could not take the build: a memory region overflowed (``RAM
   overflow``), or twister filtered the board out. Whether that is acceptable
   is a safety-case decision, not made here.
``build-only``
   twister built the test but did not run it (``build_only`` in the scenario).
``unexplained``
   Anything else: a ztest skip whose ``depends_on`` holds, cannot be evaluated
   (``depends_met`` ``n/a``), or is not recorded. These are the findings below.

Skips by class and board
========================

.. skipclasscounts::

Unexplained skips
=================

Grouped by test module.

.. needtable::
   :filter: type == "test_result" and skip_class == "unexplained"
   :columns: test_module, id, platform, reason, depends_met, result_of
   :sort: test_module
   :style: table

Ran although the condition was false
====================================

Results that did not skip although their build did not meet the test case's
``depends_on`` (``depends_met`` ``no``): the test ran, or failed, where the
specification says it does not apply. Each one is a finding.

.. needtable::
   :filter: type == "test_result" and depends_met == "no" and status != "skipped"
   :columns: test_module, id, platform, status, result_of
   :sort: test_module
   :style: table
