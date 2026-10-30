----------------------------- MODULE SelfChain -----------------------------
(***************************************************************************)
(* Known answer for an INSTANCE ... WITH chain of three modules. M <- 3    *)
(* gives N = 6 in SelfChainC, so c has 6 values and b has 2: 12 distinct   *)
(* states. The search reaches c = 5 in 5 steps: depth 6. A wrong           *)
(* substitution (for example N <- M) gives a different count.              *)
(***************************************************************************)
EXTENDS Naturals

VARIABLES b, c

B == INSTANCE SelfChainB WITH M <- 3

Spec == B!Init /\ [][B!Next]_<<b, c>>
TypeOK == b \in BOOLEAN /\ c \in 0..5
=============================================================================
