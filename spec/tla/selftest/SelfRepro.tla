---------------------------- MODULE SelfRepro ----------------------------
(***************************************************************************)
(* Known answer for the reproducibility of -fp 0. The state has a set and  *)
(* a function, the kinds of values that TLC must normalize (tlaplus issue  *)
(* #1445). The run script runs this model twice, and the two runs must     *)
(* give the same distinct states and depth as the recorded values.         *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

VARIABLES s, f
vars == <<s, f>>

Init == s = {} /\ f = [i \in 1..3 |-> 0]

Add == \E e \in 1..6 \ s : s' = s \cup {e} /\ UNCHANGED f
Drop == s # {} /\ s' = s \ {CHOOSE e \in s : \A d \in s : e <= d}
             /\ UNCHANGED f
Bump == \E i \in 1..3 : f' = [f EXCEPT ![i] = (@ + Cardinality(s)) % 4]
             /\ UNCHANGED s
Next == Add \/ Drop \/ Bump
Spec == Init /\ [][Next]_vars

TypeOK == s \subseteq 1..6 /\ f \in [1..3 -> 0..3]
=============================================================================
