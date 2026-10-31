Counterexample diagrams
#######################

Each figure in this chapter shows one counterexample of TLC as a timing
diagram. Each counterexample is a finding of the chapter
:doc:`formal-model`. The configuration of each figure is a line of
``spec/tla/mc/expected.txt`` with an expected violation.

How to read a figure:

- Time goes from left to right. The part between two dashed lines is one
  step of TLC. The width of a part is not a time.
- The lanes at the top show the state of the scheduler: the run queue, the
  cache ``ready_q.cache`` and the interrupt mask (BASEPRI).
- The lanes below show the ISRs and the threads, from high to low priority.
  A box gives the kernel function or the state of the thread in that step.
- The label at the top right names the violated property and its
  requirement.

Source of the figures
*********************

A prototype generator in the workspace notes made the figures on
2026-10-29. It reads the TLC trace of a configuration, selects a template
for each step and writes a timing diagram. The ``timeline-viz`` tool of the
latency benchmarks draws the SVG file. The commands of the generator are::

   python3 tla2tdl.py run <id>      # TLC run of the configuration, one worker
   python3 tla2tdl.py build <id>    # the timing diagram and the SVG file

Headless Chromium made the PNG file of each figure (for the PDF)::

   chromium-browser --headless --force-device-scale-factor=2 \
       --window-size=<width>,<height> --screenshot=<id>.png <id>.svg

The figures are copies in ``diagrams/``. The documentation build does not
make them again. On 2026-10-31 the check of the generator
(``python3 tla2tdl.py check``) found no change in the TLA+ definitions that
its templates follow (``spec/tla`` at commit ``6283adf``). It also found no
error in its 120 code locations at Zephyr ``770fdef1567``.

P7-a: a priority change of the current thread acts as a yield
*************************************************************

.. figure:: diagrams/p7_tie.*
   :alt: Timing diagram of P7-a
   :width: 100%

   P7-a: ``k_thread_priority_set(self, same priority)`` acts as a yield
   (``CONFIG_USE_SWITCH=y``). Configuration ``MCScheduler_p7_tie.cfg``,
   property :need:`PROP-Scheduler-TieGoesToLongestReady`.

t1, t2 and t3 have the same priority, and t1 became ready first. t1 sets
its own priority to the same value. ``z_thread_prio_set()`` puts t1 at the
tail, ``update_cache(1)`` takes the head t2, and the reschedule switches at
once. :need:`ZEP-SRS-2-13` is violated.

P7-b: a priority change of another thread preempts a cooperative thread
***********************************************************************

.. figure:: diagrams/p7_coop.*
   :alt: Timing diagram of P7-b
   :width: 100%

   P7-b: ``k_thread_priority_set()`` of another thread preempts a
   cooperative thread (``CONFIG_USE_SWITCH=y``). Configuration
   ``MCScheduler_p7_coop.cfg``, property
   :need:`PROP-Scheduler-CoopKeepsCpu`.

Up to the end of step 2 the kernel is correct: t3 has the higher priority,
but the cooperative t2 keeps the CPU (``update_cache(0)``). Then t2 sets the
priority of t1 to the same value. The run queue order does not change. Only
``preempt_ok = 1`` makes t3 the cache, and t2 loses the CPU.
:need:`ZEP-SRS-2-14` is violated. The trace does not name the waker in
step 2. The diagram shows an ISR.

P7-c: an abort of another thread preempts a cooperative thread
**************************************************************

.. figure:: diagrams/p7_abort.*
   :alt: Timing diagram of P7-c
   :width: 100%

   P7-c: ``k_thread_abort()`` of another thread preempts a cooperative
   thread (``CONFIG_USE_SWITCH=y``). Configuration
   ``MCScheduler_p7_abort.cfg``, property
   :need:`PROP-Scheduler-CoopKeepsCpu`.

t2 is cooperative and keeps the CPU after the wake of t3 (step 2, correct).
In step 3 an ISR aborts t1: ``halt_thread()`` calls ``update_cache(1)``, the
cache becomes t3, and the exit of the same ISR switches to t3.
:need:`ZEP-SRS-2-14` is violated.

P2-w: an unlock after a wake under an outer interrupt lock does not preempt
***************************************************************************

.. figure:: diagrams/p2_window.*
   :alt: Timing diagram of P2-w
   :width: 100%

   P2-w: ``irq_unlock()`` after a wake under ``irq_lock()`` does not
   preempt (``CONFIG_USE_SWITCH=y``). Configuration
   ``MCScheduler_p2_window.cfg``, property
   :need:`PROP-Scheduler-UnlockPreempts`.

t1 holds an outer ``irq_lock()`` and wakes t3 (higher priority).
``z_reschedule()`` does not switch: the key is the raised BASEPRI.
``irq_unlock()`` only writes BASEPRI. t1 keeps the CPU while the cache is
t3. :need:`ZEP-SRS-2-9` is violated at the unlock (reading L1).

SW-1: an ISR before PendSV gives the CPU back to a cooperative waiter
*********************************************************************

.. figure:: diagrams/gap_coop_pendsv.*
   :alt: Timing diagram of SW-1
   :width: 100%

   SW-1: an ISR before PendSV gives the CPU back to a cooperative waiter
   (``arch_swap()``, PendSV). Configuration
   ``MCScheduler_gap_coop_pendsv.cfg``, property
   :need:`PROP-Scheduler-BlockedLosesCpu`.

t2 waits on o1 after t3. ``arch_swap()`` sets PendSV pending and unlocks.
Before PendSV runs, the ISR wakes all waiters: ``update_cache(0)`` keeps the
cache at ``_current`` t2, because t2 is ready and cooperative again. PendSV
then gives the CPU back to t2 while t3 (higher priority) is ready.
:need:`ZEP-SRS-2-12` and :need:`ZEP-SRS-2-14` are violated (candidate
finding).

F14: an abort makes a joiner ready and does not reschedule
**********************************************************

.. figure:: diagrams/f14_join.*
   :alt: Timing diagram of F14
   :width: 100%

   F14: ``k_thread_abort()`` makes a joiner ready and does not reschedule
   (``CONFIG_USE_SWITCH=y``). Configuration ``MCScheduler_f14_join.cfg``,
   property :need:`PROP-Scheduler-PreemptibleRunsHighest`.

t3 joins t2. t1 aborts t2: ``unpend_all()`` makes t3 ready with 0, and
``update_cache(1)`` makes it the cache. The abort of another thread does
not reschedule, so t1 keeps the CPU while t3 has a higher priority.
:need:`ZEP-SRS-2-9` is violated in the last state.

P6-u: an init of an object with a waiter
****************************************

.. figure:: diagrams/p6_init.*
   :alt: Timing diagram of P6-u
   :width: 100%

   P6-u: ``k_sem_init()`` of an object with a waiter (undefined behavior).
   Configuration ``MCScheduler_p6_init.cfg``, property
   :need:`PROP-Scheduler-NoUndefined`.

t1 waits on o1. t2 calls ``k_sem_init(o1)``: ``z_waitq_init()`` empties the
wait queue without a look at the waiters. t1 keeps ``pended_on``, and no
wake of o1 finds it. The model stops with ``panic = "undefined"``. The
property has no ``@source``: it is a condition of use.
