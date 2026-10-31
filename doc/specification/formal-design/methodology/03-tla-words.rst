3. TLA+ words, as the method uses them
======================================

- **Module**: a TLA+ module. Each module is one ``.tla`` file with the same name. Other meanings are
  written in full: Zephyr module, log module, Python module, CMake module.
- **Specification**: all modules of the library ``spec/tla/``.
- **Constant**, **variable**: the declarations of a module with ``CONSTANT`` and ``VARIABLE``. An
  **ASSUME** states a condition on the constants.
- **State**: one value for each variable. **Behavior**: a sequence of states. **Step**: two
  consecutive states of a behavior. A constant has the same value in all states of a behavior.
- **Operator**: a named definition, ``Op(x) == ...``. An **action** is an operator that contains
  primed variables. It relates a state to the next state.
- **Initial predicate**: the operator ``Init``. It gives the first state of each behavior.
- **Next-state relation**: the operator ``Next``, a disjunction of actions. Each step of a behavior
  matches one of its disjuncts.
- **Spec**: the formula ``Init /\ [][Next]_vars``, with the fairness conditions. Its behaviors are
  the behaviors of the module.
- **Property**: a formula that each behavior must satisfy. An **invariant** is true in each state.
  An **action property** is true for each step. A **liveness property** states that something
  occurs in the end. A ``Spec`` **satisfies** a property if each of its behaviors satisfies the
  property.
- **INSTANCE**, **EXTENDS**: the two ways for a module to use another module. ``INSTANCE`` is for
  a module with variables, ``EXTENDS`` for a module without variables.
- **Refinement mapping**: an expression for each variable of module B, written in the variables of
  module A. Module A **refines** module B if each behavior of A, seen through the mapping, is a
  behavior of B. Then each property of B also holds for A.
- **TLC**: the model checker of TLA+. **Model checking** examines all behaviors of a finite
  instance of a module. A **configuration** (``.cfg`` file) fixes the constants, the bounds and the
  properties to check. A **TLC run** checks one configuration. A **counterexample** is a behavior
  that violates a property.
- **Model-check module** (``mc/MC<Module>.tla``): a module that sets the constants, the selectors
  and the bounds of another module for TLC, and adds probes (section 9.1). It instantiates the
  client module of that module, if one exists (section 5.1). It adds no step of the code and no
  assumption of use. One model-check module has one or more configurations.
- **History variable**: a variable that a module adds only to record the past of a behavior. It
  does not change the behaviors of the other variables. Examples: ``readySince`` of ``Scheduler``,
  ``bad`` of the open form (section 9.5).
- **Model**: only in "model checking" and "model-check module". C code is never a model.
