Requirements Traceability
=========================

Covered Requirements
--------------------

Requirements that have at least one test case linked to them.

.. needtable::
   :filter: type == "requirement" and links_back
   :columns: ID, TITLE, LINKS INCOMING
   :style: DATATABLES

Coverage Gaps
-------------

Requirements not yet covered by any test case.

.. needtable::
   :filter: type == "requirement" and not links_back
   :columns: ID, TITLE
   :style: DATATABLES
