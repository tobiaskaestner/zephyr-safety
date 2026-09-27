Requirements Traceability
=========================

Covered Requirements
--------------------

Requirements that have at least one test case linked to them.

.. needtable::
   :filter: type == "req" and verifies_back
   :columns: id, title, verifies_back
   :style: DATATABLES

Coverage Gaps
-------------

Requirements not yet covered by any test case.

.. needtable::
   :filter: type == "req" and not verifies_back
   :columns: id, title
   :style: DATATABLES
