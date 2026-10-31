14. Decisions
=============

Accepted during the reading of 2026-10-29:

- The guiding principle with "kernel function in scope", the list of functions without a
  definition, and the rule query / step action (sections 6, 9.3).
- Candidate finding and triage (section 8). One description for each kind of test (9.2).
- Refinement trees with leaves, "more abstract / more concrete" only inside a tree, "higher /
  lower" only for components. "Representation" for the data axis. Each leaf shows one aspect of
  the code. The exception "fine uses fine" (5.2).
- One table for each kind of piece. The organization words leave the method (section 11).
- "Module" means one ``.tla`` file (section 3).
- No rank number. Five ordered layers with the client layer on top. "Client" only for applications
  (section 2). The fourth layer is the "kernel API" layer.
- "Uses" at two levels with the matching rule, at most one contract module for each component.
  "Provides / requires" leave the method (5.1, for now).
- Parts in each module, world and grain assumptions, condition of use for the client or the
  product, detector, probes in the model-check module (section 6, 9.1).
- The role names parameter, variable, query, helper, step action, sub-action and environment
  action. The defining module gives the role (section 6, for now).
- Each module defines ``Init``, ``Next`` and ``Spec`` with the most general environment. The model-check
  module only sets constants and bounds, and adds probes. Model mutants go into a mutant module
  (sections 3, 6, 9.1).
- Tests on the real code: test double, fake, shadow header and reference fake defined in 9.2. A
  fake contains world assumptions and cannot check them. Only four kinds of module define a
  next-state relation (9.2).
- The guiding principle in the defined words, "satisfies", the evidence scope of a result, the
  test for the grain assumption, and the dependency of evidence on the used components (3, 9.3).
- Identifiers: the prefix table of section 10, with ``WA-`` and ``CU-``. Findings keep their old names
  after ``F-``. Readings get letters.
- Kconfig categories with names, "fault model" in place of "check". Configuration only for TLC,
  scenario only for twister, product for one set of Kconfig values (section 7).
- Findings: a divergence between the code and a requirement, or between two requirements. A
  candidate finding comes from a counterexample of a property or of a refinement. Four classes,
  and "open" for a finding without a class (section 8).
- Model checking: ``mc/expected.txt`` as the only record of expected results, refinement checks
  named by the more concrete module, mutant modules, example test modules are not model-check
  modules (section 9.1).

Open:

1. The property part stays in the contract module (section 6). A separate file is necessary only if
   a module more abstract than the contract module ever exists.
2. Grain: name ``<Module>_<Reason>``, tag ``@grain fine``, and each edge of a tree with a reason.
3. The behavior invariants in the behavior part, and the ``@source`` rule (section 6).
4. Component (for "contract group"), unit, caller.
5. Template module for ``Waitable``. "Layer A" and "layer B" leave the method. Submodule for a part
   of a contract module.
6. Where it goes: a page "Architecture of the formal specification" in the architecture document
   (next to ``formal-model.rst``), and the glossary in ``spec/tla/README.rst``. The roadmap refers to
   it and uses only these words.

Held back (2026-10-30):

- Where the list of kernel functions without a definition is kept. Proposal: a tag
  ``@c-none <function>: <reason>`` in the contract module.
- How a property names its reading. Proposal: a tag ``@reading RD-...`` next to ``@source``.
