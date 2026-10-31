10. Identifiers
===============

One prefix for each kind of record, unique in the whole method. Today F1, R1, C1, P7 and D1 each
have several meanings (inventory conflict 5).

.. list-table::
   :header-rows: 1

   * - Prefix
     - Record
     - Example
   * - (none)
     - finding (register)
     - Each existing id stays (F1 to F14, P7-a, P2-w, SW-1, P6-u, D1 to D3, TS-1), because app names, commits and tests use them (D13). A new finding gets a short topic id, as TS-1. The fields of D7 carry the source and the method.
   * - ``OC-``, ``SEM-``, ``MUTEX-`` and others
     - finding of a unit test app
     - The prefix names the unit (D13). The old ``F-1`` of ``obj_core`` becomes ``OC-1``.
   * - ``RD-``
     - reading of a requirement
     - RD-2-9-a, RD-2-9-b. The register notes the old names (L1, G1).
   * - ``WA-``
     - world assumption
     - WA-1. The tag in the module gives the ID, so a renamed operator keeps it.
   * - ``AoU-``
     - assumption of use (D26, replaces ``CU-``)
     - AoU-1, AoU-H. The tag in the module gives the ID, as for ``WA-``.
   * - ``RF-``
     - divergence of the reference fake from the code
     - RF-6
   * - ``TDL-``
     - limit of a test double
     - TDL-17
   * - ``O-``
     - design observation
     - O-1
   * - ``Q-``, ``C-``
     - question, check question of a decision
     - kept, but only inside their document
