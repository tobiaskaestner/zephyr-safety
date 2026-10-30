---------------------------- MODULE PlatformTest ----------------------------
(***************************************************************************)
(* Example tests of lib/Platform.tla (see WaitQueueTest for the method).   *)
(* The tests fix the queries of the platform for single states: the        *)
(* in-ISR state, the interrupt lock and its key, the switch variant, a     *)
(* pending PendSV and the properties of the module. The actions IrqLock,   *)
(* IrqUnlock, RequestPendSV and PendSVRuns have primes: the models         *)
(* (mc/MCScheduler) check them.                                            *)
(***************************************************************************)
EXTENDS Integers, TLC

\* The platform with one CPU c1, the variant us (UseSwitch), the nesting n
\* of the outer lock of c1 and the flag pv (PendSV pending on c1).
At(us, n, pv) ==
    INSTANCE Platform WITH Threads <- {"t1", "t2"}, CPUS <- {"c1"}, Isrs <- {"i1"},
        IsrCpu <- [i \in {"i1"} |-> "c1"], MaxIrqNest <- 2, UseSwitch <- us,
        irqNest <- [c \in {"c1"} |-> n], pendsv <- [c \in {"c1"} |-> pv]

\* A test: the value got must be the value want.
Check(name, got, want) == Assert(got = want, <<name, "got", got, "want", want>>)

\* The queries in fixed states. An instance with parameters cannot be the
\* value of a definition, so each wrapper applies At with "!".
InIsr(a)          == At(TRUE, 0, FALSE)!InIsr(a)
Actors            == At(TRUE, 0, FALSE)!Actors
Locked(n)         == At(TRUE, n, FALSE)!Locked("c1")
Key(n)            == At(TRUE, 0, FALSE)!Key(n)
KeyUnlocked(n)    == At(TRUE, n, FALSE)!KeyUnlocked("c1")
IrqCanRun(n)      == At(TRUE, n, FALSE)!IrqCanRun("c1")
ClockCanFire(n)   == At(TRUE, n, FALSE)!ClockCanFire("c1")
AtOnce(us)        == At(us, 0, FALSE)!SwitchAtOnce
Pending(us, pv)   == At(us, 0, pv)!SwitchPending("c1")
TypeOK(us, n, pv) == At(us, n, pv)!TypeOK
NoPendSVWithSwitch(us, pv)  == At(us, 0, pv)!NoPendSVWithSwitch
PendingIsUnlocked(n, pv)    == At(FALSE, n, pv)!PendingIsUnlocked

-----------------------------------------------------------------------------
(* The tests *)

\* The actors and arch_is_in_isr(): at coarse grain the kind of the actor.
TestActors ==
    /\ Check("actors",         Actors, {"t1", "t2", "i1"})
    /\ Check("in isr: isr",    InIsr("i1"), TRUE)
    /\ Check("in isr: thread", InIsr("t1"), FALSE)

\* The interrupt lock: the nesting and the key. Only the key of the outer
\* call is "unlocked", so only its irq_unlock() unlocks the CPU.
TestLock ==
    /\ Check("lock: none",             Locked(0), FALSE)
    /\ Check("lock: one",              Locked(1), TRUE)
    /\ Check("lock: nested",           Locked(2), TRUE)
    /\ Check("key: outer call",        Key(0), "unlocked")
    /\ Check("key: nested call",       Key(1), "locked")
    /\ Check("key: unlocked if no lock", KeyUnlocked(0), TRUE)
    /\ Check("key: locked under a lock", KeyUnlocked(1), FALSE)
    \* irq_unlock() of the last call restores the key of that call: the
    \* CPU is unlocked after it only if the nesting was 1.
    /\ Check("unlock: last of one",    Key(1 - 1) = "unlocked", TRUE)
    /\ Check("unlock: last of two",    Key(2 - 1) = "unlocked", FALSE)

\* Interrupts and clock events run only on an unlocked CPU.
TestIrqs ==
    /\ Check("irq: unlocked",   IrqCanRun(0), TRUE)
    /\ Check("irq: locked",     IrqCanRun(1), FALSE)
    /\ Check("clock: unlocked", ClockCanFire(0), TRUE)
    /\ Check("clock: locked",   ClockCanFire(2), FALSE)

\* The two variants of the switch.
TestSwitch ==
    /\ Check("switch: use_switch at once",   AtOnce(TRUE), TRUE)
    /\ Check("switch: arch_swap deferred",   AtOnce(FALSE), FALSE)
    /\ Check("switch: pendsv pending",       Pending(FALSE, TRUE), TRUE)
    /\ Check("switch: no pendsv",            Pending(FALSE, FALSE), FALSE)

\* The properties of the module in chosen states.
TestProperties ==
    /\ Check("TypeOK",                       TypeOK(FALSE, 2, TRUE), TRUE)
    /\ Check("TypeOK: nesting above bound",  TypeOK(FALSE, 3, FALSE), FALSE)
    /\ Check("NoPendSVWithSwitch holds",     NoPendSVWithSwitch(TRUE, FALSE), TRUE)
    /\ Check("NoPendSVWithSwitch fails",     NoPendSVWithSwitch(TRUE, TRUE), FALSE)
    /\ Check("NoPendSVWithSwitch arch_swap", NoPendSVWithSwitch(FALSE, TRUE), TRUE)
    /\ Check("PendingIsUnlocked holds",      PendingIsUnlocked(0, TRUE), TRUE)
    /\ Check("PendingIsUnlocked fails",      PendingIsUnlocked(1, TRUE), FALSE)

-----------------------------------------------------------------------------
(* The spec: one state, no deadlock. Its only purpose is the run of the    *)
(* invariants above.                                                       *)

VARIABLE unused
Init == unused = 0
Next == UNCHANGED unused
=============================================================================
