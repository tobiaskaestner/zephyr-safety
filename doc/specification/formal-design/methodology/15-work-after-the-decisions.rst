15. Work after the decisions
============================

1. Write the architecture page and the glossary in the safety repo.
2. Rename in the specs, the doc extension (``@level`` to ``@grain``, the role from ``Next`` and
   ``@source``) and its tests, the README, the roadmap, the unit map (``units.yaml`` fields, "level",
   "client") and the register (IDs). Add a grep check for the old words in CI, as for the
   forbidden names.
3. Move ``Init``, ``Next`` and ``Spec`` from the model-check modules into the modules (``Scheduler``,
   ``Timeout``, ``WaitQueue``). Write the restrictions of today's configurations as conditions of use.
   Move the model mutants into mutant modules. Make ``mc/expected.txt`` the only record of the
   expected results. Keep the expected results, or explain each change.
4. Regenerate the module map with the view of section 12.
5. Rewrite the roadmap from step 2.0 on in the new words, with the architecture as the frame.
