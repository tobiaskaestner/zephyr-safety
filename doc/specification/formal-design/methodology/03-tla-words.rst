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
- **Model-check module** (``mc/MC<Module>.tla``): a module that sets the constants and the bounds of
  another module for TLC. It uses the ``Spec`` of that module and does not define a ``Next`` of its
  own. One model-check module has one or more configurations.
- **Model**: only in "model checking" and "model-check module". C code is never a model.
