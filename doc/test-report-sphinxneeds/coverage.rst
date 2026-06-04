Test Coverage
#############

Covered test cases
==================

Test cases for which at least one test result exists in this report.

.. needtable::
   :filter: type == "test_case" and len(links_back) > 0
   :columns: id, title, test_module, suite, links_back
   :style: table

Fully passed test cases
=======================

Test cases where every test result in this report has status ``passed``.

.. needtable::
   :filter: type == "test_case" and len(links_back) > 0 and all(needs[r]["status"] == "passed" for r in links_back if r in needs)
   :columns: id, title, test_module, suite, links_back
   :style: table

Not covered test cases
======================

Test cases for which no test result exists in this report.

.. needtable::
   :filter: type == "test_case" and len(links_back) == 0
   :columns: id, title, test_module, suite, status
   :style: table
