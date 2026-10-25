Kconfig reference
=================

This page lists the Kconfig options of the suite. The common options are
in ``common/Kconfig``. Each measurement app sources that file from its own
``Kconfig`` and adds its own options. In an experiment file, write an
option without the ``CONFIG_`` prefix (see
:ref:`benchguide-experiment-file`).

Common options
--------------

.. list-table::
   :header-rows: 1
   :widths: 38 12 50

   * - Option
     - Default
     - Meaning
   * - ``LATBENCH_SAMPLES``
     - 100000
     - Number of samples in one repetition
   * - ``LATBENCH_WARMUP``
     - 16
     - Number of samples that the app discards at the start
   * - ``LATBENCH_CODE_PAD_BYTES``
     - 0
     - Bytes of code padding before the app and kernel code (a multiple
       of 4, see :doc:`common`)
   * - ``LATBENCH_HIST_BINS``
     - 4096
     - Number of 1-cycle bins (range 1 to 65536)
   * - ``LATBENCH_HIST_COARSE_BINS``
     - 0
     - Number of coarse bins after the 1-cycle bins
   * - ``LATBENCH_HIST_COARSE_SHIFT``
     - 5
     - log2 of the width of a coarse bin (range 1 to 12)
   * - ``LATBENCH_PHASE_BINS``
     - 64
     - Number of bins of a phase histogram
   * - ``LATBENCH_STIM_RANDOM``
     - y
     - Choice ``LATBENCH_STIM_MODE``: random time between two edges
   * - ``LATBENCH_STIM_FIXED``
     - n
     - Choice ``LATBENCH_STIM_MODE``: fixed period
   * - ``LATBENCH_STIM_PERIOD_US``
     - 300
     - Period of the fixed stimulus in microseconds (only with
       ``LATBENCH_STIM_FIXED``)
   * - ``LATBENCH_STIM_PERIOD_ADJ_CYC``
     - 1
     - Counts of the stimulus timer added to the fixed period (range -10000
       to 10000, only with ``LATBENCH_STIM_FIXED``)

Load generators
---------------

.. list-table::
   :header-rows: 1
   :widths: 38 12 50

   * - Option
     - Default
     - Meaning
   * - ``LATBENCH_LOAD_THREADS``
     - 0
     - Number of load threads (range 0 to 64)
   * - ``LATBENCH_LOAD_THREAD_BLOCKED``
     - y
     - Choice ``LATBENCH_LOAD_THREAD_KIND``: each thread waits forever on a
       semaphore
   * - ``LATBENCH_LOAD_THREAD_SLEEPER``
     - n
     - Choice ``LATBENCH_LOAD_THREAD_KIND``: each thread sleeps for a random
       time, in a loop
   * - ``LATBENCH_LOAD_THREAD_BUSY``
     - n
     - Choice ``LATBENCH_LOAD_THREAD_KIND``: busy loop at the lowest
       application priority
   * - ``LATBENCH_LOAD_THREAD_PRIO``
     - 5
     - Priority of the blocked and the sleeper threads
   * - ``LATBENCH_LOAD_THREAD_STACK``
     - 384
     - Stack size of a load thread in bytes
   * - ``LATBENCH_LOAD_SLEEP_MIN_MS``
     - 1
     - Minimum sleep of a sleeper thread (only with
       ``LATBENCH_LOAD_THREAD_SLEEPER``)
   * - ``LATBENCH_LOAD_SLEEP_MAX_MS``
     - 20
     - Maximum sleep of a sleeper thread (only with
       ``LATBENCH_LOAD_THREAD_SLEEPER``)
   * - ``LATBENCH_LOAD_TIMERS``
     - 0
     - Number of load timers (range 0 to 512)
   * - ``LATBENCH_LOAD_TIMER_PERIODIC``
     - y
     - Choice ``LATBENCH_LOAD_TIMER_KIND``: periodic, random period and
       start
   * - ``LATBENCH_LOAD_TIMER_FAR``
     - n
     - Choice ``LATBENCH_LOAD_TIMER_KIND``: one-shot, one hour from the start
   * - ``LATBENCH_LOAD_TIMER_MIN_MS``
     - 10
     - Minimum period of a periodic timer (only with
       ``LATBENCH_LOAD_TIMER_PERIODIC``)
   * - ``LATBENCH_LOAD_TIMER_MAX_MS``
     - 100
     - Maximum period of a periodic timer (only with
       ``LATBENCH_LOAD_TIMER_PERIODIC``)
   * - ``LATBENCH_SYSTICK_PRIO``
     - -1
     - IRQ priority of SysTick, in the numbers of ``IRQ_CONNECT()``. The
       value -1 keeps the driver default (0). Only with
       ``CONFIG_CORTEX_M_SYSTICK``.

Options of each app
-------------------

Each measurement app defines the limits of the random stimulus and the
poll period of its main thread. ``stim.c`` uses
``LATBENCH_STIM_MIN_US`` and ``LATBENCH_STIM_MAX_US``, so a new app with the
stimulus must define them too.

.. list-table::
   :header-rows: 1
   :widths: 30 14 14 14 28

   * - Option
     - ``irq_latency``
     - ``wake_latency``
     - ``thread_latency``
     - Meaning
   * - ``LATBENCH_STIM_MIN_US``
     - 200
     - 100
     - 100
     - Minimum time between two edges (only with ``LATBENCH_STIM_RANDOM``)
   * - ``LATBENCH_STIM_MAX_US``
     - 1000
     - 500
     - 500
     - Maximum time between two edges (only with ``LATBENCH_STIM_RANDOM``)
   * - ``LATBENCH_POLL_MS``
     - 100
     - 100
     - 100
     - Poll period of the main thread in milliseconds

``irq_latency``:

The interrupt path must be on the CMake command line, because
``CMakeLists.txt`` selects the overlay of the port from it (see
:doc:`apps`).

.. list-table::
   :header-rows: 1
   :widths: 38 12 50

   * - Option
     - Default
     - Meaning
   * - ``LATBENCH_IRQ_PATH_STOCK``
     - y
     - Choice ``LATBENCH_IRQ_PATH``: GPIO driver callback
   * - ``LATBENCH_IRQ_PATH_WRAPPED``
     - n
     - Choice ``LATBENCH_IRQ_PATH``: own ISR through ``_isr_wrapper``
   * - ``LATBENCH_IRQ_PATH_DIRECT``
     - n
     - Choice ``LATBENCH_IRQ_PATH``: own direct ISR
   * - ``LATBENCH_IRQ_PATH_ZLI``
     - n
     - Choice ``LATBENCH_IRQ_PATH``: own direct zero-latency ISR (selects
       ``ZERO_LATENCY_IRQS``)
   * - ``LATBENCH_BG_IDLE``
     - y
     - Choice ``LATBENCH_BACKGROUND``: idle thread (WFI)
   * - ``LATBENCH_BG_BUSY``
     - n
     - Choice ``LATBENCH_BACKGROUND``: busy thread at the lowest priority

``wake_latency``:

.. list-table::
   :header-rows: 1
   :widths: 38 12 50

   * - Option
     - Default
     - Meaning
   * - ``LATBENCH_WAKE_ISR_WRAPPED``
     - y
     - Choice ``LATBENCH_WAKE_ISR``: ``IRQ_CONNECT()``
   * - ``LATBENCH_WAKE_ISR_DIRECT``
     - n
     - Choice ``LATBENCH_WAKE_ISR``: ``IRQ_DIRECT_CONNECT()``, reschedule at
       the exit
   * - ``LATBENCH_WAKE_SEM``
     - y
     - Choice ``LATBENCH_WAKE_PRIMITIVE``: semaphore
   * - ``LATBENCH_WAKE_EVENT``
     - n
     - Choice ``LATBENCH_WAKE_PRIMITIVE``: event (selects ``EVENTS``)
   * - ``LATBENCH_WAKE_MSGQ``
     - n
     - Choice ``LATBENCH_WAKE_PRIMITIVE``: message queue
   * - ``LATBENCH_WAKE_FIFO``
     - n
     - Choice ``LATBENCH_WAKE_PRIMITIVE``: FIFO
   * - ``LATBENCH_WAKE_POLL``
     - n
     - Choice ``LATBENCH_WAKE_PRIMITIVE``: poll signal (selects ``POLL``)
   * - ``LATBENCH_WAKE_PRIO``
     - 0
     - Priority of the woken thread
   * - ``LATBENCH_BG_IDLE``, ``LATBENCH_BG_BUSY``
     - y, n
     - Choice ``LATBENCH_BACKGROUND``, as in ``irq_latency``

``thread_latency``:

.. list-table::
   :header-rows: 1
   :widths: 38 12 50

   * - Option
     - Default
     - Meaning
   * - ``LATBENCH_T2T_SEM``
     - y
     - Choice ``LATBENCH_T2T_PRIMITIVE``: semaphore
   * - ``LATBENCH_T2T_MUTEX``, ``LATBENCH_T2T_CONDVAR``,
       ``LATBENCH_T2T_EVENT``, ``LATBENCH_T2T_MSGQ``, ``LATBENCH_T2T_FIFO``,
       ``LATBENCH_T2T_LIFO``, ``LATBENCH_T2T_STACK``, ``LATBENCH_T2T_POLL``,
       ``LATBENCH_T2T_WORK``, ``LATBENCH_T2T_WAKEUP``
     - n
     - Choice ``LATBENCH_T2T_PRIMITIVE``: the other primitives (see
       :doc:`apps`). ``EVENT`` selects ``EVENTS``, and ``POLL`` selects
       ``POLL``.
   * - ``LATBENCH_T2T_PREEMPT``
     - y
     - y: the taker (priority 1) preempts the giver (priority 2). n: the
       taker has priority 3.

Settings in ``prj.conf``
------------------------

Each measurement app sets ``CONFIG_ASSERT=n`` and
``CONFIG_SPIN_VALIDATE=n`` in its ``prj.conf``, because the two trees have
different defaults for these options (see :doc:`pitfalls`).
``wake_latency`` and ``thread_latency`` set
``CONFIG_MAIN_THREAD_PRIORITY=10``, so that the main thread does not compete
with the measured threads.

A board port can add a Kconfig fragment ``port.conf``. The port of the
NUCLEO-G474RE sets ``CONFIG_CORTEX_M_SYSTICK_64BIT_CYCLE_COUNTER=y`` (see
:doc:`hardware`).
