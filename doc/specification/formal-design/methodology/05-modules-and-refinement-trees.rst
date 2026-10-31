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
- **Uses** (between modules): a module uses a contract module through ``INSTANCE`` or ``EXTENDS``. A
  module sees a hook as a constant operator, not as an ``INSTANCE``. The higher component gives the
  operator. (Replaces "provides / requires" of draft 2 and "contract above / below".)
- Rule: each ``INSTANCE`` or ``EXTENDS`` between modules matches an edge of the uses graph. A uses
  edge between two components with the same contract module is not an ``INSTANCE``. A script can
  check this rule against ``units.yaml``, as one more drift check.
- **World module**: the contract module of the world layer (``Platform``). It describes the hardware
  and the arch code.
- **Template module**: a module without a component of its own. The contract modules of several
  components **instantiate** it, because the components share a structure. Example: ``Waitable`` for
  the objects. (Replaces "layer B". "Layer A" becomes "the contract module of the scheduler".)
- **Client module**: the module of a client. It uses the contract modules of the kernel API layer, as
  they use the contract module of the scheduler.

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
  root is the contract module, at coarse grain. Each other module refines exactly one **parent**,
  the next module toward the root. A module with two parents gives no new evidence, because
  refinement is transitive.
- **More abstract**, **more concrete**: the order in a refinement tree, over both axes. The root
  is the most abstract module. Only modules in one tree are more abstract or more concrete, never
  higher or lower.
- **Reason**: each edge of a refinement tree states its reason. The reason is the aspect of the
  code that the more concrete module shows and its parent hides: the boundaries that it splits,
  the representation that it adds, or both. Examples: the SMP lock order, interrupt nesting, the
  dlist of the run queue.
- **Fine module**: a module at fine grain in a refinement tree. Name ``<Module>_<Reason>``, for
  example ``Scheduler_SmpLocks``, tag ``@grain fine``.
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

Today each refinement tree has one module. No fine module and no refinement of the representation
exist yet. The ``Backend`` constant of ``Timeout`` (DLIST or MINHEAP) is not a refinement. It selects
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

     client       a client module (planned)
                       | uses
     kernel API   group services: Thread, SchedApi, TimeSlice, ...
                  group objects:  KSem, KMutex, ...  (each instantiates the template module Waitable)
                       | uses
     scheduler    Scheduler
                       | uses
     foundation   WaitQueue, Timeout, ...
                       | uses
     world        Platform

     hooks go up as constant operators (for example the slice reset)
