Hierarchy
=========

The system requirements (``ZEP-SYRS-*``) and the software requirements
(``ZEP-SRS-*``) that refine them. A software requirement names its system
requirements in ``trace``.

.. list-table::
   :header-rows: 1

   * - Requirements
     - Count
   * - system requirements
     - :need_count:`type == 'req' and id.startswith('ZEP-SYRS-')`
   * - system requirements with no software requirement
     - :need_count:`type == 'req' and id.startswith('ZEP-SYRS-') and len(trace_back) == 0`
   * - software requirements
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-')`
   * - software requirements with no system requirement
     - :need_count:`type == 'req' and id.startswith('ZEP-SRS-') and len(trace) == 0`

System requirements with no software requirement
------------------------------------------------

.. needtable::
   :filter: type == 'req' and id.startswith('ZEP-SYRS-') and len(trace_back) == 0
   :columns: id; title
   :style: table
   :sort: id

Software requirements with no system requirement
------------------------------------------------

.. needtable::
   :filter: type == 'req' and id.startswith('ZEP-SRS-') and len(trace) == 0
   :columns: id; title; component
   :style: table
   :sort: id

System requirement × software requirements
------------------------------------------

.. needtable::
   :filter: type == 'req' and id.startswith('ZEP-SYRS-')
   :columns: id; title; trace_back as "refined by"
   :style: table
   :sort: id
