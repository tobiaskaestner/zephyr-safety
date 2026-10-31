Appendix: history
=================

- Draft 1: the dimensions and the first decision list.
- Draft 2: data abstraction as its own dimension (inventory TR:481), the roles (the inventory found
  properties of the code inside the "normative layer", SC:904), restricted "model",
  "configuration" and "scenario", the ID rule, and separate terms for assumption, condition of use
  and premise.
- Draft 3: each term is defined before its first use. Refinement trees, representation, and the
  three relations. Five layers
  with the client layer, no rank number. "Module" is one ``.tla`` file. Role names step action and
  environment action.
- Draft 4 (2026-10-31): applies the decisions D1 to D37 to the text, without markers. "Assumption
  of use" (``AoU-``) replaces "condition of use" (``CU-``). Client modules in ``clients/``, abstract
  modules in ``abstract/``, hooks through ``obs`` with three rules, ``@grain`` in the module header.
  The transitivity sentence of 5.2 is corrected, and the coarse modules are for one CPU. New
  sections 5.3 (fairness of a fine module, no prophecy variable), 5.4 (time), 9.4 (the records of
  the evidence: studies and experiments) and 9.5 (the open form of the claim, timing claims as
  safety bounds). Selectors, bounds, the VIEW rule and vacuity probes in 9.1. The scope of the
  trace checks in 9.2. Triage and the fields of the register in section 8. The new identifiers of
  findings in section 10. Section 15 lists the changes of the specs that are still to do.
