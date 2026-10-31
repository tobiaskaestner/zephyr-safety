2. The code side
================

- **Scope**: the C files of the kernel that the safety case covers. These are 43 files in
  ``kernel/``, the clock and SysTick drivers, and the headers that they include. A **kernel
  function in scope** is a C function in these files.

- **Kconfig option**: an option of the Kconfig system of Zephyr. A **product** is one set of values for all
  Kconfig options. Which code a product runs depends on these values.

- **Component**: the code in scope that shares one state under one lock, and that the other code
  sees as one thing. A component can contain C files, parts of C files and headers. Example: the
  scheduler component is ``sched.c``, the scheduler part of ``scheduler.c``, ``ksched.h``, ``kswap.h``,
  ``metairq.h`` and ``scheduler.h``. (Replaces "contract group".)

- **Unit**: the part of one C file that belongs to one component. Most units are a whole C file.
  Three files are split between two components (``smp/ipi.c``, ``usage.c``, ``kthread.h``). A unit test
  app tests one C file.

- **Uses graph**: a graph with one node for each component, and an edge from A to B if code of A
  calls code of B. A is then a **caller** of B. Without changes, all 26 components in scope are in
  one cycle.

- **Cut**: an edge of the uses graph that the method removes to break the cycles. The call stays
  in the code. The list is ``meta.cut_edges`` in ``units.yaml`` of the unit map (workspace notes).

- **Higher**, **lower**: after the cuts, the uses graph has no cycle. Component A is higher than
  component B if a path of edges goes from A to B. This is a partial order, not a number. Only
  components are higher or lower. (Replaces "level 0..11" of the unit map and "rank" of draft 2.
  The longest path decided those numbers. On one CPU, ``Ipi`` is empty, and all numbers above it
  changed.)

- **Hook**: a call on a cut edge. Most hooks go from a lower component to a higher one, for
  example the slice reset from the scheduler to the time slice. The lower component calls a
  function that the higher component gives, and it does not depend on the higher component.

- **Client**: an application on top of the kernel. It calls the kernel through the kernel API. "Client"
  has no other meaning in the method.

- **Layer**: one of five ordered groups of components. Rule: an edge of the uses graph never goes
  to a higher layer. Inside a layer, edges can go in both directions.

  .. list-table::
     :header-rows: 1

     * - Layer
       - Groups
       - Components (unit map)
     * - client
       -
       - the applications
     * - kernel API
       - services
       - TimeSlice, Idle, ObjRegistry, Thread, SchedApi, Fatal, Userspace, Boot
     * -
       - objects
       - Sem, Mutex, Event, MemSlab, Pipe, KHeap, Timer, Futex, CondVar, MsgQ, Queue, Stack, Mailbox, Work, Poll
     * - scheduler
       -
       - Scheduler
     * - foundation
       -
       - SysClock, TimeoutQueue, SchedLock, Usage, Timeout, ThreadState, RunQueue, WaitQueue, Ipi
     * - world
       -
       - Platform (hardware and arch code), Device

  Services and objects are two groups of one layer, because they use each other in both
  directions. For example, ``Userspace`` uses ``MsgQ``, and ``Work`` uses ``Thread``. The unit map of
  2026-10-28 has no edge against the layer order.
