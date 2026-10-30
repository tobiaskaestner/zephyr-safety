---------------------------- MODULE SelfNoInit ----------------------------
(***************************************************************************)
(* Known answer: no initial state. TLC reports "No error has been found"   *)
(* for this model (tlaplus issue #1475), and the run script must report    *)
(* no-states, not pass.                                                    *)
(***************************************************************************)
EXTENDS Naturals

VARIABLE x

Init == x \in 1..3 /\ x > 5
Next == x' = x + 1
Spec == Init /\ [][Next]_x

TypeOK == x \in Nat
=============================================================================
