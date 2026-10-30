----------------------------- MODULE SelfFair -----------------------------
(***************************************************************************)
(* Known answers for fairness. x counts from 0 to 3 and then stops. With   *)
(* weak fairness, each behavior reaches x = 3. Without fairness, a         *)
(* behavior that stutters for ever before x = 3 is a counterexample.       *)
(***************************************************************************)
EXTENDS Naturals

VARIABLE x

Init == x = 0
Next == x < 3 /\ x' = x + 1
FairSpec == Init /\ [][Next]_x /\ WF_x(Next)
UnfairSpec == Init /\ [][Next]_x

ReachesThree == <>(x = 3)
=============================================================================
