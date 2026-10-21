References
==========

- Module: :tla:mod:`KSem`, :tla:mod:`Extra`.
- Definition with module: :tla:def:`KSem!Give`, :tla:def:`Extra!++`.
- Definition by unique name: :tla:def:`Enqueue`.
- Property: :tla:def:`KSem!NoWaitWhileAvailable`.
- Need: :need:`PROP-KSem-NoWaitWhileAvailable`.
- Code block with the Unicode lexer:

  .. code-block:: tla-unicode

     Inv == /\ x \in Nat
            /\ x' >= x

- Code block with the ASCII lexer:

  .. code-block:: tla

     Inv == /\ x \in Nat
