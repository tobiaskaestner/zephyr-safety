---------------------------- MODULE MCKSemMutants ----------------------------
(***************************************************************************)
(* The model mutants of objects/KSem.tla. Each mutant is KSem!Next with    *)
(* one step action replaced (design note: model mutants are not in the     *)
(* module). Each one must violate a property of KSem; its line in          *)
(* mc/expected.txt names the property.                                     *)
(*                                                                         *)
(* - give_counts: a give that hands the semaphore over to a waiter also    *)
(*   increments the count (mutant give_counts_and_wakes of the proof of    *)
(*   concept). Expected: TokenConservation fails.                          *)
(* - pend_split: a take with the count 0 releases sem_lock first, and the  *)
(*   thread enters the wait queue in a later step, without a new look at   *)
(*   the count (PendAtomic = FALSE of the proof of concept). This breaks   *)
(*   the grain assumption of the take. Expected: NoWaitWhileAvailable      *)
(*   fails (a give between the two steps increments the count while the    *)
(*   thread then waits).                                                   *)
(* - reset_wakes_one: k_sem_reset() with "if" in place of "while": one     *)
(*   waiter is woken (mutant reset_if_not_while of the proof of concept).  *)
(*   Expected: ResetWakesAll fails.                                        *)
(***************************************************************************)
EXTENDS MCKSem

CONSTANT MCMutant

VARIABLE
    \* pend_split: the wait that a thread decided under the lock and has not
    \* started yet, <<object, timeout>>, or <<>>.
    split

mvars == <<vars, split>>

-----------------------------------------------------------------------------
(* give_counts *)

MutGive(o, a) ==
    /\ r[o].init
    /\ panic = "none"
    /\ K!S!CanCall(a)
    /\ IF K!S!HasWaiters(o)
         THEN LET t  == K!S!WQ!Best(o)
                  c0 == r[o].count
                  x1 == K!SemSettle(r[o])
              IN
              /\ K!S!WakeFirst(o, K!OK, NoD)
              /\ K!S!Release(a, "resched")
              \* The mutation: the count also increments.
              /\ r' = [r EXCEPT ![o] = x1]
              /\ obs' = K!W!Obs(a, "give", o, "none",
                              <<K!W!LockCall(o, c0), K!W!WakeCall(o, K!OK, TRUE, c0, t),
                                K!W!ReleaseCall("resched", o, x1.count)>>, K!NoRet, {t})
              /\ tokens' = [tokens EXCEPT ![o] = @ + 1]
              /\ UNCHANGED req
         ELSE K!Give(o, a)

-----------------------------------------------------------------------------
(* pend_split *)

\* A thread with a split wait does nothing else until the wait starts.
NotSplit(a) == IF a \in MCThreads THEN split[a] = <<>> ELSE TRUE

\* The first half: the decision to wait and the release of sem_lock.
TakeDecide(o, a, to) ==
    /\ r[o].init
    /\ panic = "none"
    /\ a \in MCThreads
    /\ K!S!CanCall(a)
    /\ split[a] = <<>>
    /\ r[o].count = 0
    /\ to # "NO_WAIT"
    /\ K!W!ReleaseOnly(a, "unlock")
    /\ split' = [split EXCEPT ![a] = <<o, to>>]
    /\ obs' = K!W!Obs(a, "take", o, to,
                    <<K!W!LockCall(o, 0), K!W!ReleaseCall("unlock", o, 0)>>, K!NoRet, {})
    /\ UNCHANGED <<r, req, tokens>>

\* The second half: the thread enters the wait queue (without the lock).
TakePend(a) ==
    /\ panic = "none"
    /\ a \in MCThreads
    /\ split[a] # <<>>
    /\ K!S!CanCall(a)
    /\ LET o == split[a][1]
           to == split[a][2]
       IN  /\ K!S!PendCurr(a, o, to)
           /\ req' = [req EXCEPT ![a] = o]
           /\ obs' = K!W!Obs(a, "take", o, to, <<K!W!PendCall(o, to, 0)>>, K!NoRet, {})
    /\ split' = [split EXCEPT ![a] = <<>>]
    /\ UNCHANGED <<r, tokens>>

-----------------------------------------------------------------------------
(* reset_wakes_one *)

MutReset(o, a) ==
    /\ r[o].init
    /\ panic = "none"
    /\ K!S!CanCall(a)
    /\ IF K!S!HasWaiters(o)
         THEN LET t  == K!S!WQ!Best(o)
                  c0 == r[o].count
              IN
              /\ K!S!WakeFirst(o, K!EAGAIN, NoD)
              /\ r' = [r EXCEPT ![o] = K!SemFlushR(r[o])]
              /\ K!S!Release(a, "resched")
              /\ obs' = K!W!Obs(a, "flush", o, "none",
                              <<K!W!LockCall(o, c0), K!W!WakeCall(o, K!EAGAIN, TRUE, c0, t),
                                K!W!ReleaseCall("resched", o, 0)>>, K!NoRet, {t})
              /\ tokens' = [tokens EXCEPT ![o] = @ - r[o].count]
              /\ UNCHANGED req
         ELSE K!Reset(o, a)

-----------------------------------------------------------------------------

MInit == K!Init /\ split = [t \in MCThreads |-> <<>>]

\* The API steps of KSem, with the actor not in a split wait.
Unsplit(A) == A /\ NotSplit(obs'.actor) /\ UNCHANGED split

MNext ==
    \/ Unsplit(K!InitNext)
    \/ Unsplit(IF MCMutant = "give_counts"
                 THEN \E o \in MCSems, a \in K!Actors : MutGive(o, a)
                 ELSE K!GiveNext)
    \/ Unsplit(K!TakeNext)
    \/ Unsplit(IF MCMutant = "reset_wakes_one"
                 THEN \E o \in MCSems, a \in K!Actors : MutReset(o, a)
                 ELSE K!ResetNext)
    \/ Unsplit(K!ReturnNext)
    \/ K!Env /\ UNCHANGED split
    \/ K!Halted /\ UNCHANGED split
    \/ /\ MCMutant = "pend_split"
       /\ \/ \E o \in MCSems, a \in MCThreads, to \in {"FOREVER", "TICKS"} : TakeDecide(o, a, to)
          \/ \E a \in MCThreads : TakePend(a)

\* In pend_split, the take with the count 0 and a timeout is the split one:
\* the KSem take that waits in one step (lock, then z_pend_curr()) is not
\* in the mutant. The second half of the split take has only the call of
\* z_pend_curr().
MSpec == MInit /\ [][MNext /\ (MCMutant = "pend_split" =>
                                   ~(obs'.op = "take" /\ Len(obs'.calls) = 2
                                     /\ obs'.calls[2].fn = K!W!PendFn))]_mvars

MViewNoObs == <<ViewNoObs, split>>

\* A probe of pend_split: a thread decides to wait.
Reach_Split == \A t \in MCThreads : split[t] = <<>>
=============================================================================
