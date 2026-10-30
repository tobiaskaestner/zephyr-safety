---------------------------- MODULE SelfChoose ----------------------------
(***************************************************************************)
(* Known answers for CHOOSE and ASSUME. For K = 7, exactly one n in 0..20  *)
(* satisfies the predicate of Root: n = 7. For K = 11, the ASSUME is       *)
(* false, and TLC must stop with an error before the search.               *)
(***************************************************************************)
EXTENDS Naturals

CONSTANT K
ASSUME K \in 1..10

Root == CHOOSE n \in 0..20 : n * n = K * K /\ n > 0

VARIABLE v

Init == v = Root
Next == UNCHANGED v
Spec == Init /\ [][Next]_v

IsRoot == v = 7
=============================================================================
