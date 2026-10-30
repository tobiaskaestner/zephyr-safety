---------------------------- MODULE SelfLasso ----------------------------
(***************************************************************************)
(* Known answer for a liveness violation under weak fairness. x goes       *)
(* around 0, 1, 2 for ever, and never gets the value 3. Weak fairness      *)
(* excludes the behavior that stutters, so the only counterexample is the  *)
(* lasso 0, 1, 2 and back to state 1.                                      *)
(***************************************************************************)
EXTENDS Naturals

VARIABLE x

Init == x = 0
Next == x' = (x + 1) % 3
Spec == Init /\ [][Next]_x /\ WF_x(Next)

ReachesThree == <>(x = 3)
=============================================================================
