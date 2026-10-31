5. Modules and refinement trees
===============================

5.1 The modules of a component
------------------------------

- **Contract module**: the module of a component. It states what the component gives to its
  callers. Each component has at most one contract module. A contract module can cover more than
  one component. Example: today ``Scheduler.tla`` also covers ``ThreadState``, ``RunQueue`` and
  ``SchedLock``. When a covered component gets its own file, that file is its contract module. The
  proposed ``RunQueue.tla`` is such a file.
- **Submodule**: a part of a contract module in its own file that is not a component of its own.
  It exists only because of the size rule (about 400 code lines). No submodule exists today. (Replaces "slice"
  in this sense.)
- **Status** of a contract module: implemented, planned, or proof of concept. A component without
  a contract module has the status planned.
- **Uses** (between modules): a module uses a contract module through ``INSTANCE`` or ``EXTENDS``.
  (Replaces "provides / requires" of draft 2 and "contract above / below".)
- A hook goes through ``obs``, the record of the last step (D12). The lower module records the
  hook call in ``obs'`` of its step: the name, the arguments, the count and the cost. The higher
  module defines its step as the step of the lower module and, if ``obs'`` contains the call, its
  own change in the same step. A call whose result the caller tests is not a hook but a uses edge.
  Three rules apply:

  - One writer of ``obs'`` in each step: the lowest module that takes part in the step writes it.
    Each higher module reads ``obs'`` and adds its own fields with ``EXCEPT``.
  - No definition reads the unprimed ``obs``, except ``vars``, ``Init``, the type invariant, the
    probes and the trace module.
  - The fairness subscript of a module has no ``obs``. A step that changes only ``obs`` does not
    satisfy a fairness condition.
- Rule: each ``INSTANCE`` or ``EXTENDS`` between modules matches an edge of the uses graph. A uses
  edge between two components with the same contract module is not an ``INSTANCE``. A script can
  check this rule against ``units.yaml``, as one more drift check.
- **World module**: the contract module of the world layer (``Platform``). It describes the hardware
  and the arch code. It is a **board family module**: it covers one board family. Today this is
  Cortex-M with BASEPRI (ARMv7-M and ARMv8-M Mainline, D3). The evidence scope of each result names
  the family.
- **Template module**: a module without a component of its own. The contract modules of several
  components **instantiate** it, because the components share a structure. Example: ``Waitable`` for
  the objects. (Replaces "layer B". "Layer A" becomes "the contract module of the scheduler".)
- **Client module**: the module of a client, in the folder ``clients/``, for example
  ``clients/KSemClient.tla`` (D27). It uses the contract modules of the kernel API layer, as they
  use the contract module of the scheduler. Its guards are the assumptions of use of the client
  (section 6). The model-check module instantiates it. A kernel module never has such a guard.
- **Abstract module**: a module above a contract module, at coarse grain, with a reduced
  representation (D17). It is in the folder ``abstract/`` (D25). It exists only when the state
  space of a component needs it. The contract module refines it. The property part stays in the
  contract module.

5.2 Grain, representation and the refinement tree
-------------------------------------------------

- **Grain**: how much code one step of a module is.

  - **Coarse**: one critical section of the code is one step.
  - **Fine**: the module splits some boundaries into separate steps: lock acquire and lock
    release, interrupt entry and exit, the window of a lock release.

- **Representation**: how a module keeps the state of the code. Examples: a set with stamps, a
  list, an rbtree. Even a coarse module has a representation: ``WaitQueue`` keeps a set with stamps,
  not the dlist or the rbtree of the code.
- Grain and representation are the two axes of refinement. A module that is finer in grain, or
  closer to the code in representation, or both, can refine a module that is not.
- **Refinement tree**: the modules that describe the same component, ordered by *refines*. The
  root is the most abstract module: the contract module, or an abstract module above it. Each
  other module refines one **parent**, the next module toward the root. One parent is a choice for
  each refinement check, not a law. A module can also refine a second module that does not refine
  the first. That check is evidence of its own, so the structure can be a lattice.
- **More abstract**, **more concrete**: the order in a refinement tree, over both axes. The root
  is the most abstract module. Only modules in one tree are more abstract or more concrete, never
  higher or lower.
- **Reason**: each edge of a refinement tree states its reason. The reason is the aspect of the
  code that the more concrete module shows and its parent hides: the boundaries that it splits,
  the representation that it adds, or both. Examples: the SMP lock order, interrupt nesting, the
  dlist of the run queue.
- **Fine module**: a module at fine grain in a refinement tree. Name ``<Module>_<Reason>``, for
  example ``Scheduler_SmpLocks``. The name pattern is for the fine modules only.
- **Tag** ``@grain``: the header of each module states its grain, ``@grain coarse`` or
  ``@grain fine`` (D24). An action has the tag only where its grain differs from the grain of its
  module.
- A coarse module is for one CPU by construction. On SMP, one step of ``k_sem_give`` spans two
  locks, so no coarse step matches it.
- **Leaf**: a module of a refinement tree without a more concrete module. When a tree has one
  module, the root is also the leaf.
- **Abstracts**: the relation from an action or an operator to a kernel function in scope. The
  action follows the code, also where the code is surprising. Tag: ``@c-function``. Each module of a
  refinement tree abstracts the code of its component, at its own grain and representation. So
  the code has many abstractions, and each leaf shows one aspect of the code. A leaf can apply to
  some products only, for example an SMP module only to SMP products.

The uses graph and the refinement trees meet at the interface of a component. A module uses only
the contract module of a lower component, that is, the root of its tree. So a component sees a
lower component only at coarse grain and in its most abstract representation. The fine modules
stay inside their trees. Exception: a fine module can use the fine module of a lower component, if
its reason needs it. An example is the lock order of two components on SMP.

A step of a higher component often calls a lower component inside the same critical section. For
example, ``k_sem_give`` wakes a thread through the scheduler. At coarse grain, the whole call is one
step.

Today each refinement tree has one module. No fine module, no abstract module and no refinement of
the representation exist yet. The ``Backend`` constant of ``Timeout`` (DLIST or MINHEAP) is not a refinement. It selects
one of two data structures in one module.

Figure 1, the refinement tree of one component (planned modules, names as examples):

::

                         Scheduler                  root, contract module: coarse, sets with stamps
                        /          \
      Scheduler_SmpLocks            Scheduler_IrqNesting       fine, two different reasons (leaf)
                |
      Scheduler_SmpLocks_List                                   also the dlist of the run queue (leaf)

Figure 2, the contract modules in the layers. Each arrow ends at a contract module. "Up" and "down"
mean the uses graph only.

::

     client       client modules (planned, for example clients/KSemClient.tla)
                       | uses
     kernel API   group services: Thread, SchedApi, TimeSlice, ...
                  group objects:  KSem, KMutex, ...  (each instantiates the template module Waitable)
                       | uses
     scheduler    Scheduler
                       | uses
     foundation   WaitQueue, Timeout, ...
                       | uses
     world        Platform

     hooks go up through obs (for example the slice reset)

5.3 Fairness of a fine module, and auxiliary variables
-------------------------------------------------------

A fine module splits a coarse step into fine steps. Weak fairness of the coarse step then becomes
weak fairness of the last fine step, plus the condition that the fine steps of one split run to
the end. The rule (D30):

- The fairness conditions of a fine module are weak fairness on its own exit steps and on
  ``PendSV``. The fine module writes them with its own variables as the subscript, never through
  ``INSTANCE ... WITH``.
- TLC checks the safety part ``Refines`` of the refinement check through the mapping.
- The liveness part ``RefinesFair`` rests on a written argument: weak fairness on the last fine
  step of each split gives the weak fairness of the coarse step, if the fine steps of one split
  run to the end. The liveness configuration of the fine module checks this premise.

The world assumptions and assumptions of use behind the rule, on one CPU (Cortex-M with BASEPRI).
Each one has a tag ``@assumption`` in ``Platform``:

1. The NVIC takes a pending and enabled exception with a priority above BASEPRI in bounded time.
   Tail chaining changes no order. This gives weak fairness on each step "interrupt entry".
2. Each ISR returns. This is an assumption of use for the ISRs of the client. It gives weak
   fairness on each step "interrupt exit".
3. The interrupt load is not continuous: between two steps of a thread, only a finite number of
   interrupt entries occur. This is an assumption of use of the product.
4. The nesting depth is bounded by the number of priority levels in use. ``MaxIrqNest`` is then a
   constant of the product, not a bound of the model.
5. PendSV runs when no other exception is active (PendSV has the lowest exception priority).
6. SysTick has the highest priority of the ISRs that call the kernel. So no ISR that calls the
   kernel runs inside the announce loop, and the loop runs to its end (section 5.4).

With 1 to 3 and 5, ``WF(PendSV)`` follows.

Rule for the coarse modules (D31): a coarse module makes no choice before the step in which the
code makes it. Then a refinement mapping needs no prophecy variable. History variables are
allowed, because they keep the liveness of the spec.

5.4 Time (planned for increment 1)
----------------------------------

The model of time (D29, D32):

- Time is an integer in ticks. Increment 1 states each timing claim in ticks only. ``Platform``
  has no clock in seconds.
- The state has countdown timers, not a variable ``now``. A step ``Tick`` is a disjunct of
  ``Next``.
- **Overdue allowance** ``L``: the guard of ``Tick`` is "no entry is overdue by more than ``L``
  ticks". Each entry has a counter of its overdue ticks, because the countdown stops at 0. So the
  bound "no entry is overdue by more than ``L``" is a property that can fail.
- ``MaxAnnounce``: the number of ticks that one call of ``sys_clock_announce()`` can carry. It is a
  fact of the product and the driver. ``L`` is a fact of the client and the world. The two are
  separate constants.
- Each time bound is a safety property (section 9.5).

The announce loop (``sys_clock_announce_locked()``, ``kernel/timeout.c``):

- The loop releases ``timeout_lock`` around each expiry handler (``timeout.c:394-396`` at Zephyr
  ``770fdef1567``).
- For the thread timeouts of ``KSem`` on one CPU, one atomic announce step is exact. The SysTick
  driver gives SysTick the priority ``_IRQ_PRIO_OFFSET``
  (``drivers/timer/cortex_m_systick.c:542, 566``). ``IRQ_CONNECT()`` adds the same offset to the
  priority of each ISR (``arch/arm/core/cortex_m/irq_manage.c:122``), and an equal priority does
  not preempt. So no ISR that calls the kernel runs in the window. This is a world assumption.
  The assumption of use that remains: the application does not change the NVIC priorities other
  than through ``IRQ_CONNECT()`` and ``irq_priority_set()``.
- For ``k_timer`` and the time slice, a fine announce module is necessary. The expiry handler runs
  inside the loop with the lock released. It reads and changes the timeout state between two
  pops. A ``k_timer`` expiry function is client code.
- ``z_time_slice()`` runs after the release of ``timeout_lock`` (``timeout.c:406-410``) and takes
  the scheduler lock itself. It is a separate coarse step.
- The first experiment of the work on time measures the state-space factor of one timed entry on
  ``MCKSem default``.
