---------------------------- MODULE SelfChainB ----------------------------
(* The middle of the INSTANCE chain of SelfChain. It gives N <- 2 * M to   *)
(* SelfChainC and adds the flag b.                                         *)
EXTENDS Naturals

CONSTANT M
VARIABLES b, c

C == INSTANCE SelfChainC WITH N <- 2 * M

Init == b \in BOOLEAN /\ C!Init
Next == \/ b' = ~b /\ UNCHANGED c
        \/ C!Next /\ UNCHANGED b
=============================================================================
