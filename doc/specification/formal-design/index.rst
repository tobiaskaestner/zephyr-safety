Zephyr Kernel Formal Design Specification
#########################################

.. note::

   Status: the methodology is draft 3. The decisions D1 to D18 of
   2026-10-30 and 2026-10-31 are not applied to it yet. See the chapter
   :doc:`decisions`.

This document gives the formal design of the Zephyr kernel in the safety
scope. The design is a library of TLA+ modules in ``spec/tla`` of the safety
repository. The TLC model checker examines the modules.

The document has these parts:

- The methodology: the words of the method, the pieces of the specification,
  their relations and the evidence.
- The decisions of the user on the review of the method. The methodology
  does not apply them yet.
- The formal design model: the modules of the TLA+ library and one need for
  each model property.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   methodology/index
   decisions
   formal-model

.. toctree::
   :caption: Cross-reference test
   :maxdepth: 1

   xref-test
