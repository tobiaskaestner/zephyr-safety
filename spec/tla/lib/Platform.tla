------------------------------ MODULE Platform ------------------------------
(***************************************************************************)
(* The world below kernel/sched.c, level 1: the CPUs, the actors, the      *)
(* interrupt lock, the context switch and the clock events.                *)
(*                                                                         *)
(* This is an assumption module. It states only what sched.c relies on.    *)
(* Each item that rests on the architecture code or on a document has the  *)
(* tag @assumption with that location. No proof checks these items. The    *)
(* fakes of the arch_* layer and later the trace validation check them.    *)
(* The architecture is ARMv7-M and ARMv8-M Mainline (BASEPRI), the CPU of  *)
(* the boards G474RE and RT1060. The code locations are of Zephyr          *)
(* 770fdef1567.                                                            *)
(*                                                                         *)
(* Level 1: an ISR is one step, so "in an ISR" is the kind of the actor    *)
(* and not a variable. The interrupt lock of a CPU is the outer lock of    *)
(* the thread that runs on it (irq_lock() outside a kernel call). The      *)
(* spinlocks inside a kernel call are a part of the step. Level 2 adds the *)
(* IPIs, the lock owners and the ISR nesting.                              *)
(*                                                                         *)
(* The context switch has two variants (UseSwitch). With                   *)
(* CONFIG_USE_SWITCH the decision and the switch are in one step. With     *)
(* arch_swap() the step only sets PendSV pending, and a later step PendSV  *)
(* selects the thread. Between the two steps ISRs can run: the             *)
(* "non-atomic swap" of CONFIG_SWAP_NONATOMIC. On one CPU both variants    *)
(* select the cache _kernel.ready_q.cache. Only the time of the decision   *)
(* is different.                                                           *)
(***************************************************************************)
EXTENDS Integers, FiniteSets

CONSTANTS
    \* The threads: the actors that are not ISRs.
    \* @type: Set(THREAD);
    Threads,
    \* The ISR actors of the objects (not the timer ISR of the expiry).
    \* @type: Set(THREAD);
    Isrs,
    \* The CPU of each ISR.
    \* @type: THREAD -> CPU;
    IsrCpu,
    \* The maximum number of nested irq_lock() calls in a model. This is a
    \* bound of the model, not a Kconfig option.
    \* @type: Int;
    MaxIrqNest

\* The CPUs. A set with one CPU is a uniprocessor: CONFIG_SMP=n and
\* CONFIG_MP_MAX_NUM_CPUS=1. A set with two CPUs is CONFIG_SMP=y (design
\* exploration at level 1). CONFIG_SMP=y with one CPU is not in the model.
\* This is a Kconfig option of kind 2: each model configuration fixes the
\* set.
\* @kconfig CONFIG_SMP CONFIG_MP_MAX_NUM_CPUS
\* @type: Set(CPU);
CONSTANT CPUS

\* The variant of the context switch. TRUE: CONFIG_USE_SWITCH=y,
\* z_swap() calls arch_switch() (arm_m_switch() on Cortex-M) and the exit
\* of an interrupt calls arm_m_must_switch(). FALSE: CONFIG_USE_SWITCH=n,
\* z_swap() calls arch_swap() and the switch is in the PendSV handler.
\* This is a Kconfig option of kind 2 (it changes the behavior): each
\* model configuration fixes its value. The default on Cortex-M is FALSE.
\* CONFIG_SWAP_NONATOMIC is y on each Cortex-M, also with
\* CONFIG_USE_SWITCH (arch/arm/core/Kconfig:34), so the model has no
\* constant for it: the gap before PendSV comes from arch_swap().
\* @kconfig CONFIG_USE_SWITCH
\* @assumption arch/arm/core/Kconfig:34 (CONFIG_SWAP_NONATOMIC is y for each Cortex-M)
\* @type: Bool;
CONSTANT UseSwitch

VARIABLES
    \* The number of irq_lock() calls of the thread that runs on CPU c that
    \* no irq_unlock() has ended yet. 0: interrupts are unlocked. The model
    \* keeps the state for each CPU, because a thread must not switch while
    \* it holds the lock (see NoSwitchWhileLocked in Scheduler).
    \* @type: CPU -> Int;
    irqNest,
    \* PendSV is pending on CPU c: arch_swap() or the exit of an interrupt
    \* has set the PENDSVSET bit, and the PendSV handler has not run yet.
    \* Always FALSE with CONFIG_USE_SWITCH.
    \* @type: CPU -> Bool;
    pendsv

platVars == <<irqNest, pendsv>>

ASSUME CPUS # {}
ASSUME Isrs \cap Threads = {}
ASSUME \A i \in Isrs : IsrCpu[i] \in CPUS
ASSUME MaxIrqNest \in Nat
ASSUME UseSwitch \in BOOLEAN

\* CONFIG_SMP depends on CONFIG_USE_SWITCH. Thus the variant arch_swap()
\* has one CPU.
\* @assumption kernel/smp/Kconfig:8 (config SMP depends on USE_SWITCH)
ASSUME ~UseSwitch => Cardinality(CPUS) = 1

-----------------------------------------------------------------------------
(* The actors *)

\* An actor calls the kernel: a thread or an ISR.
Actors == Threads \cup Isrs

\* arch_is_in_isr(): actor a runs in an ISR. At level 1 an ISR is one step,
\* so this is the kind of the actor. On Cortex-M each exception counts as an
\* ISR, also a fault or the SVC of a system call.
\* @c-function arch_is_in_isr
\* @assumption arch/arm/include/cortex_m/exception.h:93 (arch_is_in_isr() reads IPSR: each exception is an ISR)
InIsr(a) == a \in Isrs

-----------------------------------------------------------------------------
(* The interrupt lock *)

\* CPU c has interrupts locked: the thread that runs on c holds an outer
\* irq_lock().
\* @assumption include/zephyr/arch/arm/asm_inline_gcc.h:56-57 (arch_irq_lock() raises BASEPRI to _EXC_IRQ_DEFAULT_PRIO: no interrupt that calls the kernel runs)
Locked(c) == irqNest[c] > 0

\* The key that irq_lock() (or k_spin_lock()) returns on a CPU with the
\* nesting n: the state before the call. irq_unlock(key) restores this
\* state, so only the key of the first, outer call unlocks the CPU.
\* @c-function arch_irq_lock
\* @assumption include/zephyr/arch/arm/asm_inline_gcc.h:56 (the key is the old BASEPRI)
Key(n) == IF n = 0 THEN "unlocked" ELSE "locked"

\* arch_irq_unlocked(key) for the key of a lock that a kernel call takes on
\* CPU c now. For an ISR the key is "unlocked" too: an ISR that calls the
\* kernel runs only while its CPU is unlocked, and the exception entry does
\* not change BASEPRI.
\* @c-function arch_irq_unlocked
\* @assumption include/zephyr/arch/arm/asm_inline_gcc.h:102-106 (a key is unlocked if it is 0)
KeyUnlocked(c) == Key(irqNest[c]) = "unlocked"

\* An interrupt that calls the kernel can run on CPU c. Each ISR step of the
\* model and each clock event requires it. An interrupt that becomes
\* pending while c is locked runs after the unlock, as a separate step.
\* Zero-latency interrupts do not call the kernel and are not in the model.
\* @assumption doc:kernel/services/interrupts (zero-latency interrupts must not call kernel APIs)
IrqCanRun(c) == ~Locked(c)

\* irq_lock() by the thread that runs on CPU c, outside a kernel call. The
\* calls nest (see Key). At most MaxIrqNest nested calls.
\* @kind action
\* @c-function arch_irq_lock
IrqLock(c) ==
    /\ irqNest[c] < MaxIrqNest
    /\ irqNest' = [irqNest EXCEPT ![c] = @ + 1]
    /\ UNCHANGED pendsv

\* irq_unlock(key) by the thread that runs on CPU c, with the key of its
\* last irq_lock(), Key(irqNest[c] - 1). The CPU is unlocked after the step
\* if that key is "unlocked". The call does not reschedule: on Cortex-M it
\* only writes BASEPRI.
\* @kind action
\* @c-function arch_irq_unlock
\* @assumption include/zephyr/arch/arm/asm_inline_gcc.h:80-99 (arch_irq_unlock() writes BASEPRI and calls no kernel code)
IrqUnlock(c) ==
    /\ irqNest[c] > 0
    /\ irqNest' = [irqNest EXCEPT ![c] = @ - 1]
    /\ UNCHANGED pendsv

-----------------------------------------------------------------------------
(* The context switch *)

\* The switch of a reschedule point is in the same step: CONFIG_USE_SWITCH.
\* z_swap(): do_swap() reads _kernel.ready_q.cache with interrupts locked
\* (kswap.h:112, without CONFIG_SMP) and calls arch_switch(). The exit of an
\* interrupt to thread mode: arm_m_exc_exit() calls arm_m_must_switch()
\* with BASEPRI raised. z_sched_next_handle() compares the cache with
\* _current (ksched.h:80-88), and z_get_next_switch_handle() sets _current
\* to the cache (sched.c:795-799). The new thread unlocks interrupts in
\* arm_m_switch() after the stack switch.
\* @assumption arch/arm/core/cortex_m/arm-m-switch.c:510-536 (the exit of each interrupt to thread mode calls arm_m_must_switch())
\* @assumption include/zephyr/arch/arm/arm-m-switch.h:156-195 (arm_m_exc_tail() patches the return only for a return to thread mode)
SwitchAtOnce == UseSwitch

\* A reschedule point of CPU c without CONFIG_USE_SWITCH: the step sets
\* PendSV pending if need is TRUE, and does not switch. z_swap() calls
\* arch_swap(), which sets PENDSVSET and unlocks all interrupts with
\* irq_unlock(0) (kernel_arch_func.h:87-103). Its callers call it only if
\* the cache differs from _current (need). The exit of an interrupt calls
\* z_arm_int_exit(), which sets PENDSVSET if the cache differs from
\* _current (exc_exit.c:55-61). A pending PendSV stays pending.
\* @kind action
\* @c-function arch_swap
\* @c-function z_arm_int_exit
\* @assumption arch/arm/core/cortex_m/exc_exit.c:57 (CONFIG_PREEMPT_ENABLED=y, else the exit of an interrupt never switches)
\* @assumption drivers/timer/cortex_m_systick.c:336 and arch/arm/core/cortex_m/isr_wrapper.c:97 (each ISR that calls the kernel ends with z_arm_int_exit())
RequestPendSV(c, need) ==
    /\ pendsv' = [pendsv EXCEPT ![c] = pendsv[c] \/ need]
    /\ UNCHANGED irqNest

\* A switch is pending on CPU c (arch_swap() only). No thread code runs on
\* c until PendSV runs. ISRs can run: the PendSV exception has the lowest
\* priority, so each pending interrupt runs first. This is the non-atomic
\* gap of CONFIG_SWAP_NONATOMIC.
\* @assumption arch/arm/include/cortex_m/exception.h:144-149 (PendSV has the lowest exception priority)
SwitchPending(c) == pendsv[c]

\* The PendSV handler runs on CPU c (arch_swap() only). The caller selects
\* the thread: the handler reads _kernel.ready_q.cache when it runs
\* (swap_helper.S:147), not when PendSV became pending.
\* @kind action
\* @c-function z_arm_pendsv
\* @assumption arch/arm/core/cortex_m/swap_helper.S:147 (PendSV switches to the cache as it is when the handler runs)
PendSVRuns(c) ==
    /\ pendsv[c]
    /\ IrqCanRun(c)
    /\ pendsv' = [pendsv EXCEPT ![c] = FALSE]
    /\ UNCHANGED irqNest

-----------------------------------------------------------------------------
(* Clock events and IPIs *)

\* The timer interrupt can run on CPU c (the SysTick ISR calls
\* sys_clock_announce(), which expires the timeouts). Its exit is a
\* reschedule point. The model has no clock: the expiry is an event of the
\* environment (Scheduler!ThreadTimeout). IPIs are not at level 1: level 2
\* adds them (flag_ipi(), signal_pending_ipi()), together with the lock
\* owners.
\* @assumption drivers/timer/cortex_m_systick.c:330-336 (the SysTick ISR announces the ticks and ends with z_arm_int_exit())
ClockCanFire(c) == IrqCanRun(c)

-----------------------------------------------------------------------------
(* Initial state and properties *)

\* No CPU has an outer lock, no PendSV is pending.
\* @kind definition
InitPlatform ==
    /\ irqNest = [c \in CPUS |-> 0]
    /\ pendsv = [c \in CPUS |-> FALSE]

\* @kind invariant
TypeOK ==
    /\ irqNest \in [CPUS -> 0..MaxIrqNest]
    /\ pendsv \in [CPUS -> BOOLEAN]

\* With CONFIG_USE_SWITCH no PendSV is pending: the switch has no gap.
\* @kind invariant
\* @kconfig CONFIG_USE_SWITCH
NoPendSVWithSwitch == UseSwitch => \A c \in CPUS : ~pendsv[c]

\* A switch is pending only on a CPU without an outer lock. arch_swap()
\* unlocks all interrupts, and a thread must not switch while it holds the
\* interrupt lock (the API documentation of irq_lock()).
\* @kind invariant
\* @source doc:api#irq_lock
PendingIsUnlocked == \A c \in CPUS : pendsv[c] => ~Locked(c)

=============================================================================
