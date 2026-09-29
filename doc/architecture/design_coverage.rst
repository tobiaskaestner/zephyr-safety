Design Coverage
===============

Software requirements (``ZEP-SRS-*``) against the design elements that fulfill
them and the test cases that verify them.

.. list-table::
   :header-rows: 1

   * - Software requirements
     - Count
   * - all
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-')`
   * - fulfilled by a design element
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(fulfills_back) > 0`
   * - not fulfilled by a design element
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(fulfills_back) == 0`
   * - designed, not verified
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(fulfills_back) > 0 and len(verifies_back) == 0`
   * - verified, not designed
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(verifies_back) > 0 and len(fulfills_back) == 0`
   * - neither designed nor verified
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(fulfills_back) == 0 and len(verifies_back) == 0`

Designed, not verified
----------------------

.. needtable::
   :filter: type == 'req' and id.startswith('ZEP-SRS-') and len(fulfills_back) > 0 and len(verifies_back) == 0
   :columns: id; title; fulfills_back as "fulfilled by"
   :style: table
   :sort: id

Verified, not designed
----------------------

.. needtable::
   :filter: type == 'req' and id.startswith('ZEP-SRS-') and len(verifies_back) > 0 and len(fulfills_back) == 0
   :columns: id; title; verifies_back as "verified by"
   :style: table
   :sort: id

Requirement x design
--------------------

.. needtable::
   :filter: type == 'req' and id.startswith('ZEP-SRS-')
   :columns: id; title; fulfills_back as "fulfilled by"; verifies_back as "verified by"
   :style: table
   :sort: id
