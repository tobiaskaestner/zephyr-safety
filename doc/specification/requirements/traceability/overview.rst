Overview
========

The software requirements (``ZEP-SRS-*``) per layer.

Verification
------------

.. needpie:: Software requirements verified by a test case
   :labels: verified, not verified

   type == 'req' and id.startswith('ZEP-SRS-') and len(verifies_back) > 0
   type == 'req' and id.startswith('ZEP-SRS-') and len(verifies_back) == 0

Implementation
--------------

.. needpie:: Software requirements satisfied by a symbol
   :labels: satisfied, not satisfied

   type == 'req' and id.startswith('ZEP-SRS-') and len(satisfies_back) > 0
   type == 'req' and id.startswith('ZEP-SRS-') and len(satisfies_back) == 0

Design
------

.. needpie:: Software requirements fulfilled by a design element
   :labels: designed, not designed

   type == 'req' and id.startswith('ZEP-SRS-') and len(fulfills_back) > 0
   type == 'req' and id.startswith('ZEP-SRS-') and len(fulfills_back) == 0

All layers
----------

.. list-table::
   :header-rows: 1

   * - Software requirements
     - Count
   * - all
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-')`
   * - verified
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(verifies_back) > 0`
   * - satisfied
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(satisfies_back) > 0`
   * - designed
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(fulfills_back) > 0`
   * - verified and satisfied
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(verifies_back) > 0 and len(satisfies_back) > 0`
   * - verified, satisfied and designed
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(verifies_back) > 0 and len(satisfies_back) > 0 and len(fulfills_back) > 0`
   * - none of the three
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(verifies_back) == 0 and len(satisfies_back) == 0 and len(fulfills_back) == 0`

Coverage adequacy
-----------------

One adequacy need per requirement that the coverage run can assess. The test
report explains each verdict.

.. needpie:: Adequacy verdicts
   :labels: true, partial, broken, unattributed, unresolved, no-cov, no-impl

   type == 'adequacy' and verdict == 'true'
   type == 'adequacy' and verdict == 'partial'
   type == 'adequacy' and verdict == 'broken'
   type == 'adequacy' and verdict == 'unattributed'
   type == 'adequacy' and verdict == 'unresolved'
   type == 'adequacy' and verdict == 'no-cov'
   type == 'adequacy' and verdict == 'no-impl'

.. list-table::
   :header-rows: 1

   * - Verdict
     - Requirements
   * - true
     - :need_count:`type == 'adequacy' and verdict == 'true'`
   * - partial
     - :need_count:`type == 'adequacy' and verdict == 'partial'`
   * - broken
     - :need_count:`type == 'adequacy' and verdict == 'broken'`
   * - unattributed
     - :need_count:`type == 'adequacy' and verdict == 'unattributed'`
   * - unresolved
     - :need_count:`type == 'adequacy' and verdict == 'unresolved'`
   * - no-cov
     - :need_count:`type == 'adequacy' and verdict == 'no-cov'`
   * - no-impl
     - :need_count:`type == 'adequacy' and verdict == 'no-impl'`
   * - all
     - :need_count:`type == 'adequacy'`
