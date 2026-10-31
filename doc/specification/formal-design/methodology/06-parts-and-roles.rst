6. Inside a module: parts and roles
===================================

Each definition of a module is in one of two parts, and it has one role. Each module defines its
own ``Init``, ``Next`` and ``Spec``.

- **Behavior part**: the definitions that come from the code.
- **Property part**: the definitions that come from the requirements. The property part belongs to
  the component, not to one module of its refinement tree. It is in the contract module, the
  root of the tree. Refinement carries each property down to the more concrete modules. So a
  module other than the root has only a behavior part.
- **Role**: what a definition does. The TLA+ form (tag ``@kind``) does not give the role.
- **Assumption**: a fact that the behavior takes as given and that TLC does not check. Each
  assumption has a code location. There are two kinds:

  - **world assumption**: a fact of the hardware or of the arch code. Most world assumptions are
    in the world module. Only the board and a review of the arch code check them.
  - **grain assumption**: each step of a module is atomic in the code. Each module at coarse grain
    has this assumption. A fine module or a test that the lock is held during the step checks it.

- **Condition of use**: a rule that the client or the product must obey. It goes into the safety
  manual. For a rule of the client, a client module must obey it, and TLC can show that it does.
  For a rule of the product, a configuration shows the failure when the product breaks the rule.
  Example: "do not call ``k_thread_priority_set`` under an outer interrupt lock".
- **Detector**: an invariant that names the bad state that only a client or a product that breaks
  a condition of use can reach. Examples: ``NoPanic``, ``NoUndefined``. A configuration in which the
  rule is broken shows the failure of the detector. ``NoPanic`` is a detector, not an "environment
  assumption" (inventory SC:992).
- **Premise**: the left side of an implication in a property. A premise carries a condition of use
  or a reading (for example G1, "no pending switch"). A premise is not a role.

The roles of the behavior part:

.. list-table::
   :header-rows: 1

   * - Role
     - TLA+ form
     - Meaning
   * - **parameter**
     - constant
     - the model size (``Threads``), the value of a Kconfig option of the category *behavior* (section 7), or a hook operator
   * - variable
     - variable
     - the state of the component that the module shows
   * - **query**
     - operator without a primed variable, tag ``@c-function``
     - abstracts a kernel function without side effects, for example ``Head(o)``
   * - **helper**
     - operator without a primed variable, no ``@c-function``
     - any other value or predicate of the state, for example ``Best``
   * - **step action**
     - action, a disjunct of ``Next``
     - one step of the code at the grain of the module. A kernel function that changes state becomes one or more step actions. Tag ``@c-function``.
   * - **sub-action**
     - action, not a disjunct of ``Next``
     - a part of a step action. It can combine the actions of a used module, for example ``WakeLocked`` with the changes of ``WaitQueue``.
   * - **environment action**
     - action, a disjunct of ``Next``
     - a step of the client, of the world, or of a higher component, that the module needs. Examples: an interrupt arrives, the client starts a call. Until a client module exists, the environment actions stand for the most general client.
   * - world assumption
     - operator or ``ASSUME``, tag ``@assumption``
     - see above. A grain assumption has no TLA+ form: the tag ``@grain`` of the module records it.
   * - **behavior invariant**
     - invariant without a requirement
     - a property of the code itself, for example types, ``BestIsHead``, ``ArmedArePending``, ``RunRuleHolds``. It checks the abstraction, not the design.

``Next`` contains the most general environment. Each restriction of the environment is a condition
of use, written in the module as a premise or as a guard of an environment action.

The module that defines a definition gives its role. For example, ``WaitQueue.tla`` defines the
changes of a wait queue, and ``Scheduler.tla`` defines the sub-actions that use them.

The roles of the property part:

.. list-table::
   :header-rows: 1

   * - Role
     - TLA+ form
     - Meaning
   * - **requirement property**
     - invariant, action property, liveness property
     - expresses one reading of a requirement, tag ``@source``
   * - condition of use
     - premise, or guard of an environment action, tag ``@source condition-of-use``
     - see above
   * - detector
     - invariant
     - see above, for example ``NoUndefined``

A kernel function in scope that becomes no definition (for example bookkeeping that no property can
see) is listed with its reason. Drift detection then also sees it. Section 14 holds
back the decision where the list is kept.

Tag rule (proposal): each property and each behavior invariant has exactly one ``@source``. Its value
gives the role: ``@source ZEP-SRS-...`` or ``@source doc:...`` (requirement property), ``@source condition-of-use``, ``@source code`` (behavior invariant). The doc extension shows the role.

- **Incidental choice**: a thing that the code does by chance. No requirement promises it, so the
  property part leaves it free.
