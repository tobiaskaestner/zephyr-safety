.. Copyright (c) 2026 inovex GmbH
.. SPDX-License-Identifier: Apache-2.0

CBMC check of k_sem against KSem
################################

**Status: predicate under review.** The predicates in
``tests/kernel/unit/common/include/ksem_step_pred.h`` are a hand translation
of the actions ``Give`` and ``Take`` of ``spec/tla/objects/KSem.tla``. Until a
person has reviewed each conjunct against the action (one comment for each
conjunct helps the review), a result of this check is not evidence.

What the check shows
********************

CBMC examines ``z_impl_k_sem_give()`` and ``z_impl_k_sem_take()`` of the real
``kernel/sem.c`` for all inputs: each count and limit, each wait queue up to
three threads, each timeout, each result of the scheduler stubs. For each
execution, the abstract state at the lock, the abstract state at the
release and the calls must be a step of the model (the relation
*abstracts*, for one call of one thread). The harness also checks the lock
discipline that the coarse grain of KSem needs: one lock as the first call,
one release with the key of the lock as the last call, no write of the count
or the limit before the lock or after the release. The lock stub gives the
semaphore new values (another actor ran before the lock), so a read before
the lock gives a wrong count, and the predicate fails.

The callees are stubs within the scheduler contract
(``spec/tla/lib/Scheduler.tla``). The result holds only if the real
scheduler satisfies the contract.

Files
*****

- ``ksem_harness.c``: the stubs and the two harnesses (``harness_give``,
  ``harness_take``), with vacuity probes (``-DKSEM_REACH``).
- ``run.sh``: one configuration, or ``run.sh all`` for the 16
  configurations (give and take; CONFIG_POLL on and off; LP64 and ILP32;
  with and without the runtime checks as the assumption on the start state).
- ``ilp32-gcc.sh``: the preprocessor of the ILP32 runs (the ARM gcc of the
  Zephyr SDK).

The tool is CBMC 6.8.0 (Fedora package). Run one CBMC at a time on a host
with little memory. Each run takes less than one second.

.. code-block:: console

   tests/kernel/unit/sem/cbmc/run.sh all
   CFLAGS=-DKSEM_REACH TAG=reach tests/kernel/unit/sem/cbmc/run.sh take poll lp64 rtc

Results (2026-10-30, zephyr 770fdef1567)
****************************************

- Give: the 8 configurations hold, except the unsigned overflow of
  ``sem->count +=`` without the runtime checks (count above the limit,
  finding 1 of the sem findings; the predicate holds, the model also
  wraps).
- Take: the 8 configurations hold.
- Vacuity probes: each probe fails, as it must (give: 7, take: 5).
- Take mutants (the mutants of the unit tests): ``take_busy_no_unlock``,
  ``take_ebusy_eagain``, ``take_pend_forever``, ``take_unlock_then_pend`` and
  ``take_count_dec_outside_lock`` fail; ``take_isr_assert_removed`` holds (no
  CONFIG_ASSERT in the harness: the mutant is equal to the original there).
  The give mutants: see the workspace notes (cbmc/results.md, 17 of 17).
