----------------------------- MODULE SelfSym -----------------------------
(***************************************************************************)
(* Known answers for a SYMMETRY set and for a value of a definition in the *)
(* .cfg file (the sensitivity set of mc/ uses both). Each .cfg file sets   *)
(* S = {a, b, c}, so c is a new model value. x is an element of S, and y   *)
(* changes between 0 and 1 in each step. Without symmetry: 3 x 2 = 6       *)
(* states. With the symmetry set Permutations(S), all values of x are      *)
(* equivalent: 2 states, one for each y. The depth is 2 in both cases.     *)
(* The action property Alternates holds. The invariant YIsZero fails in    *)
(* the second state of each trace, also with the symmetry set.             *)
(***************************************************************************)
EXTENDS Naturals
LOCAL INSTANCE TLC

CONSTANTS a, b

S == {a, b}

VARIABLES x, y
vars == <<x, y>>

Init == x \in S /\ y = 0
Next == x' \in S /\ y' = 1 - y
Spec == Init /\ [][Next]_vars

Perms == Permutations(S)

InS == x \in S /\ y \in {0, 1}
YIsZero == y = 0
Alternates == [][y' # y]_vars
=============================================================================
