12. The architecture view (the new map)
=======================================

- Vertical axis: the layers, world at the bottom. Inside a layer, the depth in the uses graph from
  bottom to top. The depth is a layout value only, not a term of the method.
- Left column: the units of each component. Edges *abstracts* go into the behavior half.
- Middle: the contract modules. Each box has two halves:

  - behavior half: parameters, variables, queries, helpers, step actions, sub-actions, environment
    actions, world assumptions,
    behavior invariants, code lines.
  - property half: requirement properties (with the number of ``@source`` ids), conditions of use.

- Below each box: its model-check modules with their configurations, probes and model mutants.
- Right column: the requirements by chapter. Edges *expresses* come from the property half.
- Behind a contract module, offset: its fine module, if planned, with an edge *refines*.
- Edges between modules: *uses* (``INSTANCE``, ``EXTENDS``), *hook* (dashed, up), *instantiates*
  (from an object module to the template module).
- Below each module: its configurations, example tests, contract tests, board apps, and the
  findings that they show.
- Status by the border, grain by the fill color.
