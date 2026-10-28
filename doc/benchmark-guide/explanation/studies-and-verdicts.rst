Known gaps
----------

A test for a known defect asserts the correct behavior. While the defect
is in the code, the test is an expected failure:

- In the ztest app, ``KNOWN_GAP()`` skips the test and prints
  ``KNOWN GAP:`` with the input and the result. If the result becomes
  correct, the test fails. Then remove ``KNOWN_GAP()`` from the test.
- In pytest, the test has ``xfail(strict=True)``. If the test passes,
  pytest reports a failure. Then remove the marker.

``unit/README.md`` lists the open gaps. Two gaps are open today:

- ``lat_phase_add()`` does not make sure that the phase is less than the
  period. A larger phase writes after the last bin.
- In ``lat_hist_print()``, ``sum * 100`` wraps at 2\ :sup:`64`. This occurs
  only if the sum is more than 1.8e17 cycles.
