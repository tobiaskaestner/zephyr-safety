1. Purpose, in plain words
==========================

The formal specification connects two sources: the requirements of the Zephyr kernel and its C
code. Two rules guide the work:

- Each requirement becomes a formal statement. The statement is written from the requirement, not
  from the code.
- Each function of the kernel becomes a formal description that follows the code, also where the
  code is surprising.

A model checker then shows where the described code does not satisfy the formal statements. Tests
on the real code show that the description follows the code. This section uses words in their
common meaning. Section 9 states these rules again in the words that sections 2 to 8 define.
