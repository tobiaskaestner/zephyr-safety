---------------------------- MODULE APWaitQueue ----------------------------
(***************************************************************************)
(* Inductive check of WaitQueue!StampsNormal with Apalache, on the next-  *)
(* state relation of mc/MCWaitQueue (the library module has no Next).     *)
(*                                                                         *)
(* The three obligations (tools/run_apalache.sh, apalache/expected.txt):  *)
(*                                                                         *)
(*   1. Init => IndInv          --init=Init   --inv=IndInv --length=0      *)
(*   2. IndInv /\ Next => IndInv'                                          *)
(*                              --init=IndInv --inv=IndInv --length=1      *)
(*   3. IndInv => Inv           --init=IndInv --inv=Inv    --length=0      *)
(*                                                                         *)
(* The constants are the values of MCWaitQueue_default: 3 threads, 2      *)
(* objects, 3 priorities. The values are strings in the form of the       *)
(* uninterpreted types of Apalache ("t1_OF_THREAD").                      *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

VARIABLES
    \* @type: THREAD -> OBJ;
    pendedOn,
    \* @type: THREAD -> Int;
    stamp,
    \* @type: THREAD -> Int;
    prio

\* The model of mc/MCWaitQueue, with its Init and Next.
MC == INSTANCE MCWaitQueue WITH
        t1 <- "t1_OF_THREAD", t2 <- "t2_OF_THREAD", t3 <- "t3_OF_THREAD",
        o1 <- "o1_OF_OBJ", o2 <- "o2_OF_OBJ", NoObj <- "none_OF_OBJ"

Init == MC!Init
Next == MC!Next

\* The type part of the strengthening. It is also the form that Apalache
\* needs for --init=IndInv: each variable has a set of values.
TypeDom ==
    /\ pendedOn \in [MC!Threads -> MC!Objs \cup {"none_OF_OBJ"}]
    /\ stamp \in [MC!Threads -> 0..Cardinality(MC!Threads)]
    /\ prio \in [MC!Threads -> MC!Prios]

\* The inductive invariant: the types and StampsNormal.
IndInv ==
    /\ TypeDom
    /\ MC!Inv_StampsNormal

\* The invariants to prove (obligation 3 for each one). The three order
\* invariants follow from StampsNormal in one state.
Inv            == MC!Inv_StampsNormal
InvOrderTotal  == MC!Inv_OrderIsTotal
InvRanks       == MC!Inv_RanksDistinct
InvBestIsHead  == MC!Inv_BestIsHead

\* Two weaker candidates, for the record of the strengthening (known
\* answers of apalache/expected.txt).
\* IndInvRange: StampsNormal without the condition "each stamp is unique".
\* It is inductive, but it does not imply StampsNormal (obligation 3 must
\* give a state with two waiters with the same stamp).
IndInvRange ==
    /\ TypeDom
    /\ \A t \in MC!WQ!Waiting : 1 <= stamp[t] /\ stamp[t] <= Cardinality(MC!WQ!Waiting)
    /\ \A t \in MC!Threads \ MC!WQ!Waiting : stamp[t] = 0

\* IndInvOrder: OrderIsTotal with the types, without StampsNormal. It is
\* not inductive (obligation 2 gives a counterexample to induction): a
\* waiter with the stamp 3 of 2 waiters, and an Add of a waiter with the
\* same priority to the same object gets NextStamp = 3 too.
IndInvOrder ==
    /\ TypeDom
    /\ MC!Inv_OrderIsTotal

=============================================================================
