Requirements Coverage
#####################

Requirements fully verified
===========================

Requirements for which every verifying test case has been executed and every
test result carries status ``passed``.

.. needtable::
   :filter: type == "requirement" and len(verifies_back) > 0 and all(len(needs[tc]["result_of_back"]) > 0 and all(needs[tr]["status"] == "passed" for tr in needs[tc]["result_of_back"] if tr in needs) for tc in verifies_back if tc in needs)
   :columns: id, title, verifies_back
   :style: table

Test results for fully verified requirements
--------------------------------------------

Each execution of a test case that covers a fully verified requirement,
joined on the test case ID.

.. needtable::
   :filter: type == "test_result" and len(covers) > 0 and all(needs[tc]["result_of_back"] and all(needs[tr]["status"] == "passed" for tr in needs[tc]["result_of_back"] if tr in needs) for tc in result_of if tc in needs)
   :columns: covers, result_of, id, platform, scenario, status, execution_time
   :style: table

Requirements not fully verified
================================

Requirements that have no verifying test case, have a test case with no
execution results, or have at least one test result that is not ``passed``.

.. needtable::
   :filter: type == "requirement" and not (len(verifies_back) > 0 and all(len(needs[tc]["result_of_back"]) > 0 and all(needs[tr]["status"] == "passed" for tr in needs[tc]["result_of_back"] if tr in needs) for tc in verifies_back if tc in needs))
   :columns: id, title, verifies_back
   :style: table
