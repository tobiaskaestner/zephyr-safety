Requirement × Implementation
============================

The software requirements (``ZEP-SRS-*``) against the symbols that satisfy
them (``IMPL-<symbol>``, from the API documentation and the architecture) and
the test cases that verify them.

Not satisfied by a symbol
-------------------------

.. needtable::
   :filter: type == 'req' and id.startswith('ZEP-SRS-') and len(satisfies_back) == 0
   :columns: id; title; component; verifies_back as "verified by"
   :style: table
   :sort: id

Satisfied, not verified
-----------------------

.. needtable::
   :filter: type == 'req' and id.startswith('ZEP-SRS-') and len(satisfies_back) > 0 and len(verifies_back) == 0
   :columns: id; title; component; satisfies_back as "satisfied by"
   :style: table
   :sort: id

Requirement × implementation
----------------------------

.. needtable::
   :filter: type == 'req' and id.startswith('ZEP-SRS-')
   :columns: id; title; satisfies_back as "satisfied by"; verifies_back as "verified by"
   :style: table
   :sort: id
