15. Work after the decisions
============================

The work items of draft 3:

1. Write the architecture page and the glossary in the safety repo. Done: this document and
   ``spec/tla/GLOSSARY.rst``.
2. Rename in the specs, the doc extension (``@level`` to ``@grain``, the role from ``Next`` and
   ``@source``) and its tests, the README, the roadmap, the unit map (``units.yaml`` fields, "level",
   "client") and the register (IDs). Add a grep check for the old words in CI, as for the
   forbidden names. Done for ``@grain`` and the parts (D14). The role from ``Next``, the unit map,
   the register and the grep check are still to do.
3. Move ``Init``, ``Next`` and ``Spec`` from the model-check modules into the modules (``Scheduler``,
   ``Timeout``, ``WaitQueue``). Write the restrictions of today's configurations as assumptions of
   use in client modules, selectors or bounds. Move the model mutants into mutant modules. Make
   ``mc/expected.txt`` the only record of the expected results. Keep the expected results, or
   explain each change.
4. Regenerate the module map with the view of section 12.
5. Rewrite the roadmap from step 2.0 on in the new words, with the architecture as the frame.

The work items of draft 4. Draft 4 changes the text only. These changes of the specs, the tools
and the tests are still to do:

6. The client modules (D27): ``clients/KSemClient.tla`` with the guards ``IsrWaits`` and
   ``ReInit``, and a client module of the scheduler with ``NoOuterLock``.
7. The term "assumption of use" and the ids ``AoU-<n>`` in the comments of the specs, the
   configurations and the tests (D26).
8. The tag ``@grain`` in the header of each module (D24).
9. The VIEW rule (D22): the check script, two known-answer models in ``selftest/``, and the clause
   of ``KSem!TypeOK`` that reads ``obs``.
10. The three rules of ``obs`` when ``Scheduler`` gets ``obs`` (D12).
11. The vacuity probes, as an experiment of the small-scope study (D21).
12. The study tool ``probatrix`` and the import of the existing runs (D19). Then the k_sem record
    as a page of this document that cites its runs.
13. The sensitivity set (D20): remove ``join_sens_t4``, run ``p7_rules_sens_t4_sym`` once with
    ``heap=6g``.
14. The model of time and the fine announce module for ``k_timer`` and the time slice (D29 to D35),
    after the first experiment of the work on time.
15. The rename ``OC-1`` and the unit prefixes of the unit-test findings (D13).
16. The comment of D15 next to the ``WITH`` clause of the ``Scheduler`` instance.
17. The version pin of ``Scheduler.tla`` in ``sched_ref.c`` and the defects of the drift tooling,
    together with affirmatrix (D11, D37).
