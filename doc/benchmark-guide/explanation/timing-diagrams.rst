.. _benchguide-diagrams:

How to read the timing diagrams
===============================

The timing diagrams in this guide show the sequence of one edge. They are
schematic: the width of a box does not show a duration. For measured
durations, see the histograms of a run.

- Each lane is one run context. The lanes are in three groups: the core
  (hardware and the interrupt mask), the ISRs, and the threads.
- In each group, the lane with the highest priority is at the top. The
  box next to the name gives the priority: the ``IRQ_CONNECT()`` priority
  for an ISR (``low`` for PendSV), the thread priority for a thread. Two
  lanes with the same priority have one joined box with ``=``.
- A filled box is code that runs. A dotted box is the CPU in WFI. A
  dashed box without a fill is a thread that waits: blocked, or ready
  but preempted.
- The lane ``PRIMASK, BASEPRI`` shows when the CPU masks interrupts. A
  box hatched from the lower left to the upper right is BASEPRI: kernel
  code holds ``irq_lock()`` or a spinlock. A box hatched the other way
  is PRIMASK: the idle thread sleeps in WFI with PRIMASK set, so an
  interrupt starts only after the idle thread clears it. A ZLI is not
  masked by BASEPRI, but it is masked by PRIMASK.
- The orange vertical line is the edge. A black vertical line is a time
  stamp. Its name is the name of the variable in the code.
- A bracket below the lanes is a histogram of the app. Its label is the
  name of the histogram in the output (see :doc:`../reference/log-format`).
- In the HTML output, move the pointer onto a box to see what the code
  does at that step, and which lock it holds.

The masked sections are those of the code of the pinned trees (see
:doc:`../host-tools`): the spinlocks of the kernel objects, ``stim_arm()``,
the middle part of PendSV, and the idle loop. ``_isr_wrapper``, the
STM32 EXTI and GPIO drivers and the ISR exit do not lock interrupts (with
``CONFIG_PM=n``, the default of the apps).
