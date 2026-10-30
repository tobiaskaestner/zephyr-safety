---------------------------- MODULE SelfSafety ----------------------------
(***************************************************************************)
(* Known answers for the safety checks of TLC. x counts up to 3 and goes   *)
(* back to 0. y changes freely, so each level of the search has two        *)
(* states. The shortest trace that violates Inv has 4 states (x = 0 to     *)
(* 3). The shortest trace that violates the action property Rises has 5    *)
(* states: the last step goes from x = 3 to x = 0.                         *)
(***************************************************************************)
EXTENDS Naturals

VARIABLES x, y
vars == <<x, y>>

Init == x = 0 /\ y \in {0, 1}
Next == /\ x' = IF x < 3 THEN x + 1 ELSE 0
        /\ y' \in {0, 1}
Spec == Init /\ [][Next]_vars

Inv == x < 3
Rises == [][x' > x]_x
=============================================================================
