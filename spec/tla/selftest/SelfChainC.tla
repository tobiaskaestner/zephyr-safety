---------------------------- MODULE SelfChainC ----------------------------
(* The bottom of the INSTANCE chain of SelfChain: c counts modulo N.       *)
EXTENDS Naturals

CONSTANT N
VARIABLE c

Init == c = 0
Next == c' = (c + 1) % N
=============================================================================
