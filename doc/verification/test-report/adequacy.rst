Coverage Adequacy
#################

A ``verifies`` link and a ``satisfies`` link are claims. This page checks them
against a per-test coverage run (``west twister --coverage-per-test``). For each
requirement, zdocs finds the bodies of its satisfying symbols in the sources of
the run commit. Then it compares their lines with the lines that the
requirement's own verifying tests ran.

The page assesses each requirement that has at least one verifying test case in
the run. Each requirement gets one ``adequacy`` need, with the id
``ADQ-<run>/<requirement>``. The need links to its requirement (``assesses``).
The requirement page shows the need under "assessed by".

``true``
   The own tests run every satisfying symbol that coverage can judge.
``partial``
   The own tests run some of the satisfying symbols, not all.
``broken``
   Other tests of the run reach the code. The own tests never do.
``unattributed``
   No test of the run covers any body of the symbols. Coverage cannot judge
   the link (boot-time code, inlined code, or code that the configuration
   removes).
``unresolved``
   No satisfying symbol maps to a function body. A macro has no body, so every
   requirement that only macros satisfy reads ``unresolved``.
``no-cov``
   The verifying tests ran, but the run has no coverage data for them.
``no-impl``
   No symbol satisfies the requirement.

Each need lists its symbols and their bodies (``z_impl_``, ``z_vrfy_``, a plain
definition, or a header ``static inline``). For each body, it gives the lines
that each own test ran, and the other tests that ran the body.

The coverage run is separate from the run of the test results. The coverage
run builds with instrumentation, on one board. The build sets it with
``-DZDOCS_COVERAGE_OUT=<run directory>``.

.. The run name is part of every ADQ id, so it is set here and not taken from
   a tag: a new tag on the same commit must not rename the needs. Change it
   together with -DZDOCS_COVERAGE_OUT, to the name of that run.

.. testcoverage::
   :run: twister-cov-full-run
   :layout: adequacy
