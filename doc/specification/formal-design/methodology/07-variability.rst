7. Variability
==============

- **Kconfig category**: how a Kconfig option enters the specification (method decision of
  2026-10-28, unchanged):

  - **invisible**: no effect on the specification, only a comment.
  - **behavior**: a constant and a guarded branch. Example: the ``Backend`` of ``Timeout``.
  - **condition of use**: an ``ASSUME`` or a premise, and a configuration that shows the failure.
  - **initial value**: the initial value of a variable.
  - **fault model**: the option selects panic, error code or undefined behavior. (Proposal. The
    decision of 2026-10-28 named it "check". That word collides with the checks of section 9.)

- A configuration checks one product. A **scenario** is a test case of twister (the Zephyr test
  runner, ``testcase.yaml``). The word is used only for twister. ``mc/kconfig.txt`` records which
  configuration matches which scenario.
