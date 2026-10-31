11. Summary: the dimensions
===========================

This section defines nothing new. It shows the words of sections 2 to 7 as dimensions. Each
dimension applies to one kind of piece, and no word serves two dimensions.

.. list-table::
   :header-rows: 1

   * - Piece
     - Dimension
     - Word
     - Values
     - Replaces
   * - component
     - position
     - **layer** (section 2)
     - client, kernel API, scheduler, foundation, world
     - "level 0..11", "rank", "layer A", "lane"
   * - module of a refinement tree
     - atomicity
     - **grain** (5.2)
     - coarse, fine
     - "level 1/2", "two grains", ``_L2``, ``@level 2``, "lock grain", "object grain"
   * - module of a refinement tree
     - data
     - **representation** (5.2)
     - for example a set with stamps, a list, an rbtree
     - "abstraction" (draft 3) for the data axis, "coarser view", "at the level of the model"
   * - module of a refinement tree
     - order
     - more abstract, more concrete (5.2)
     - the root is the most abstract
     - "chain" (draft 3)
   * - definition
     - source
     - **part** (6)
     - behavior part, property part
     - "descriptive / normative layer", "D / N"
   * - definition
     - function
     - **role** (6)
     - the two role tables
     - ``@kind`` alone
   * - Kconfig option
     - variability
     - **Kconfig category** (7)
     - invisible, behavior, condition of use, initial value, fault model
     - "Kconfig kind 1..5"

"Level" leaves the method. It stays only in Zephyr's own meanings (init level, interrupt priority
level, log level) and in the TLA+ meaning "expression level" of SANY, written in full.

These are attributes, not dimensions:

- The status of a contract module (5.1).
- The expected result of a configuration, and the class of a finding.
- The evidence scope of a result (9.3).

The words for the organization of the work (phase, step, item, round, vertical slice) are not part
of the method. They go into a glossary in the roadmap. "Step" in the roadmap is a step of the plan,
never a TLA+ step.
