#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0
#
# Copy of claude/kernel-unit/unit-map/.work/gen.py of the workspace notes
# (2026-10-28, the generator of units.yaml). Changes in the copy, for
# tools/uses_graph_diff.py:
# - the tree, the directory and the label are optional arguments;
# - a unit file that is not in the table T gets the entry of a file with
#   the same name, or the group "New" (the original stops);
# - the group "New" and meta.unit_files_not_in_table.
"""Write units.yaml and the cycle report from graph2.json and the tables below.

python3 -I gen.py [<zephyr> <dir> <label>]

<dir> holds graph2.json; the script writes units.yaml, cycles.json and
group_graph.json there. Without arguments: the paths of the notes.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

import yaml

import sys

if len(sys.argv) > 3:
    ZROOT, HERE, LABEL = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    OUTDIR = HERE
else:
    HERE = Path(__file__).parent
    ZROOT = Path("/wrk/z/ws-safety/zephyr")
    OUTDIR = HERE.parent
    LABEL = "zephyr @ 770fdef1567 (branch topic-safety-tskr)"
g = json.load(open(HERE / "graph2.json"))
U = g["units"]


def key(u):
    return u[len("kernel/"):] if u.startswith("kernel/") else u


# ---- purpose, build condition, group, class --------------------------------
# group = the contract that the unit gives (see unit-map.md, "Contract modules")
T = {
 "kernel/busy_wait.c": ("Implements k_busy_wait(): spins for a number of microseconds on the cycle counter or on a CPU loop.", "always", "SysClock (client: BusyWait)", "core", "drivers and the kernel use k_busy_wait() for short hardware waits."),
 "kernel/compiler_stack_protect.c": ("Gives the stack canary value and the handler that the compiler calls when a canary changes.", "CONFIG_REQUIRES_STACK_CANARIES", "Fatal (stack canary)", "out", "named out of scope by the user; it @satisfies ZEP-SRS-8-12/8-25/8-26 (open question Q4)."),
 "kernel/condvar.c": ("Implements the condition variable object (k_condvar).", "CONFIG_MULTITHREADING", "Object: CondVar", "optional", "kernel object, in scope if the application uses it; unit test exists."),
 "kernel/deadline.c": ("Implements the earliest-deadline-first API (k_thread_deadline_set) on the run queue.", "CONFIG_SCHED_DEADLINE", "SchedApi", "optional", "Kconfig feature SCHED_DEADLINE."),
 "kernel/device.c": ("Implements device init and lookup (device_init, device_is_ready, device_get_binding).", "always", "Device", "core", "every driver, also the system timer, starts through it."),
 "kernel/dynamic.c": ("Allocates and frees thread stacks at run time (k_thread_stack_alloc/free).", "CONFIG_DYNAMIC_THREAD", "ThreadLife", "optional", "Kconfig feature DYNAMIC_THREAD; dynamic memory is unusual in a safety application."),
 "kernel/dynamic_disabled.c": ("Gives stubs of k_thread_stack_alloc/free that always fail.", "!CONFIG_DYNAMIC_THREAD", "ThreadLife", "core", "the stub is in each build without dynamic threads; trivial."),
 "kernel/events.c": ("Implements the event object (k_event).", "CONFIG_EVENTS", "Object: Event", "optional", "kernel object; also used by smp/ipi.c for IPI work."),
 "kernel/fatal.c": ("Handles fatal errors: logs the reason, calls k_sys_fatal_error_handler(), then halts or aborts the faulting thread.", "always", "Fatal", "core", "the error path of each safety application."),
 "kernel/float.c": ("Implements k_float_enable/disable on top of the arch FPU sharing.", "always (code active with CONFIG_FPU_SHARING)", "Platform (FPU slice)", "optional", "FPU sharing; the three lab boards have an FPU."),
 "kernel/idle.c": ("Gives the idle thread body (loop with k_cpu_idle() and power management) and the weak default of arch_spin_relax().", "CONFIG_MULTITHREADING", "Idle", "core", "the idle thread runs when no thread is ready."),
 "kernel/init.c": ("Boots the kernel: _kernel data, device init levels, idle and main threads, switch to main.", "always", "Boot", "core", "each application starts here; gives the initial state of all modules."),
 "kernel/irq_offload.c": ("Runs a function in interrupt context through arch_irq_offload() (a test feature).", "CONFIG_IRQ_OFFLOAD", "Platform (test aid)", "out", "test feature only."),
 "kernel/kheap.c": ("Implements the k_heap object (blocking allocation from a sys_heap).", "always", "Object: KHeap", "optional", "kernel object, in scope if the application uses it."),
 "kernel/mailbox.c": ("Implements the mailbox object (k_mbox).", "CONFIG_MULTITHREADING", "Object: Mailbox", "optional", "kernel object, in scope if the application uses it."),
 "kernel/main_weak.c": ("Gives a weak empty main().", "always", "-", "out", "named out of scope by the user."),
 "kernel/mempool.c": ("Implements k_malloc/k_free, the system heap and the thread resource pools.", "CONFIG_KERNEL_MEM_POOL", "Object: KHeap (system heap)", "optional", "objects use z_thread_malloc() only for their alloc variants."),
 "kernel/mem_slab.c": ("Implements the memory slab object (k_mem_slab).", "always", "Object: MemSlab", "optional", "kernel object; unit test exists."),
 "kernel/mmu.c": ("Implements virtual memory management and demand paging.", "CONFIG_MMU", "-", "out", "no MMU on the three Cortex-M lab boards."),
 "kernel/msg_q.c": ("Implements the message queue object (k_msgq).", "CONFIG_MULTITHREADING", "Object: MsgQ", "optional", "kernel object; unit test exists."),
 "kernel/mutex.c": ("Implements the mutex object (k_mutex) with priority inheritance.", "CONFIG_MULTITHREADING", "Object: Mutex", "optional", "kernel object; unit test exists."),
 "kernel/nothread.c": ("Gives k_sleep and k_is_in_isr for builds without threads.", "!CONFIG_MULTITHREADING", "-", "out", "a safety application with threads never builds it."),
 "kernel/obj_core.c": ("Implements the object core registry and statistics (k_obj_core).", "CONFIG_OBJ_CORE", "ObjRegistry (hook)", "optional", "diagnostics; the objects and sched.c call it as a hook."),
 "kernel/pipe.c": ("Implements the pipe object (k_pipe).", "CONFIG_MULTITHREADING", "Object: Pipe", "optional", "kernel object, in scope if the application uses it."),
 "kernel/poll.c": ("Implements k_poll, poll signals, triggered work and the hook that the objects call when they change.", "CONFIG_POLL", "Object: Poll + PollHook", "optional", "Kconfig feature POLL."),
 "kernel/priority_queues.c": ("Gives the red-black tree compare function of the scalable priority queues.", "CONFIG_SCHED_SCALABLE || CONFIG_WAITQ_SCALABLE", "RunQueue, WaitQueue", "optional", "only with the scalable backends."),
 "kernel/queue.c": ("Implements the queue object (k_queue, the base of k_fifo and k_lifo).", "CONFIG_MULTITHREADING", "Object: Queue", "optional", "kernel object; unit test exists."),
 "kernel/sched.c": ("Implements the scheduler core: ready, pend, wake, reschedule, selection of the next thread, halt (suspend and abort).", "CONFIG_MULTITHREADING", "Scheduler", "core", "each thread switch goes through it."),
 "kernel/scheduler.c": ("Gives the scheduler lock (k_sched_lock/unlock), k_reschedule, the current-thread query, run queue init and the wait queue walk.", "CONFIG_MULTITHREADING", "Scheduler (walk, wait, init) + SchedApi (lock, reschedule)", "core", "k_current_get() and z_sched_init() are in each build."),
 "kernel/sem.c": ("Implements the semaphore object (k_sem).", "CONFIG_MULTITHREADING", "Object: Sem", "optional", "kernel object; unit test, CBMC harness and TLA+ PoC exist."),
 "kernel/sleep.c": ("Implements k_sleep (k_sleep_ticks): the current thread is not ready for a number of ticks.", "CONFIG_MULTITHREADING", "SchedApi", "core", "k_sleep and k_msleep are basic thread services."),
 "kernel/spinlock_validate.c": ("Checks the use of spinlocks at run time (owner, nesting).", "CONFIG_SPIN_VALIDATE", "Platform (lock checker, fine grain)", "optional", "debug check; it is the run-time form of the lock clause of the fine grain of Platform."),
 "kernel/stack.c": ("Implements the stack object (k_stack).", "CONFIG_MULTITHREADING", "Object: Stack", "optional", "kernel object; unit test exists."),
 "kernel/sys_clock_hw_cycles.c": ("Holds the hardware cycle rate when the driver reads or changes it at run time.", "CONFIG_TIMER_READS_ITS_FREQUENCY_AT_RUNTIME || CONFIG_SYSTEM_CLOCK_HW_CYCLES_PER_SEC_RUNTIME_UPDATE", "SysClock (rate)", "optional", "the lab boards use a fixed rate by default."),
 "kernel/system_work_q.c": ("Defines and starts the system work queue thread.", "CONFIG_MULTITHREADING", "Object: Work", "optional", "in scope if the application or a driver uses the system work queue."),
 "kernel/thread.c": ("Implements the thread API: create, start, names, stacks, statistics, and the scheduling calls suspend, resume, abort, join, priority, yield and wakeup.", "CONFIG_MULTITHREADING", "ThreadLife + SchedApi", "core", "each thread is created and ended through it."),
 "kernel/thread_monitor.c": ("Keeps the list of all threads and gives k_thread_foreach().", "CONFIG_THREAD_MONITOR", "ThreadLife (monitor)", "optional", "diagnostics."),
 "kernel/timeout.c": ("Implements the timeout service and the kernel tick time: add, abort, announce and uptime; it programs the system timer driver.", "CONFIG_SYS_CLOCK_EXISTS", "Timeout", "core", "each timed wait, sleep and time slice uses it."),
 "kernel/timer.c": ("Implements the timer object (k_timer).", "CONFIG_SYS_CLOCK_EXISTS", "Object: Timer", "optional", "kernel object, in scope if the application uses it."),
 "kernel/timeslicing.c": ("Implements round-robin time slices: one slice timeout for each CPU and the rotation of the current thread.", "CONFIG_TIMESLICING", "TimeSlice", "optional", "Kconfig feature TIMESLICING (default y)."),
 "kernel/usage.c": ("Measures the CPU time of threads and CPUs (thread runtime statistics).", "CONFIG_SCHED_THREAD_USAGE", "Usage (hook)", "optional", "diagnostics; the switch path calls it as a hook."),
 "kernel/version.c": ("Gives the kernel version number.", "always", "-", "out", "named out of scope by the user."),
 "kernel/work.c": ("Implements work queues and work items (k_work, k_work_delayable, k_work_queue).", "CONFIG_MULTITHREADING", "Object: Work", "optional", "service above the objects; many drivers use it."),
 "kernel/smp/cpu_mask.c": ("Implements the CPU affinity API (k_thread_cpu_mask_*, k_thread_cpu_pin).", "CONFIG_SMP && CONFIG_SCHED_CPU_MASK", "SchedApi (affinity)", "optional", "SMP only; no lab board is SMP."),
 "kernel/smp/ipi.c": ("Sends scheduler IPIs (flag, signal), handles the IPI (z_sched_ipi) and gives IPI work items.", "CONFIG_SMP", "Ipi", "optional", "SMP only."),
 "kernel/smp/smp.c": ("Starts and resumes the secondary CPUs and gives the global IRQ lock of SMP.", "CONFIG_SMP", "Platform (CPU start, fine grain)", "optional", "SMP only."),
 "kernel/sys/sem.c": ("Implements sys_sem on top of k_sem when user mode is off.", "!CONFIG_USERSPACE", "Object: Sem (client)", "optional", "thin wrapper."),
 "kernel/sys/thread_entry.c": ("Gives z_thread_entry(): the common entry of each thread; it calls the entry function and aborts the thread at return.", "always", "ThreadLife", "core", "each thread starts through it."),
 "kernel/userspace/futex.c": ("Implements futex wait and wake for user mode.", "CONFIG_USERSPACE", "Object: Futex", "optional", "user mode only."),
 "kernel/userspace/mem_domain.c": ("Implements memory domains and partitions.", "CONFIG_USERSPACE", "Userspace", "optional", "user mode only; MPU isolation can be a safety mechanism (open question Q5)."),
 "kernel/userspace/mutex.c": ("Implements the sys_mutex kernel calls on top of k_mutex.", "CONFIG_USERSPACE", "Object: Mutex (client)", "optional", "user mode only."),
 "kernel/userspace/sem.c": ("Implements sys_sem with atomics and futexes for user mode.", "CONFIG_USERSPACE", "Object: Futex (client)", "optional", "user mode only."),
 "kernel/userspace/user_work.c": ("Implements user-mode work queues on top of k_queue.", "CONFIG_USERSPACE", "Object: Work (user)", "optional", "user mode only."),
 "kernel/userspace/userspace.c": ("Implements kernel object permissions, validation, dynamic objects and the user copy helpers.", "CONFIG_USERSPACE", "Userspace + ObjRegistry (hook)", "optional", "user mode only; the objects call k_object_init() as a hook (no-op without user mode)."),
 "kernel/userspace/userspace_handler.c": ("Gives the system call handlers of the kernel object API.", "CONFIG_USERSPACE", "Userspace", "optional", "user mode only."),
 "kernel/paging/statistics.c": ("Collects demand paging statistics.", "CONFIG_DEMAND_PAGING_STATS", "-", "out", "no MMU on the lab boards."),
 "kernel/include/ipi.h": ("Declares the IPI helpers and gives the CPU mask macros.", "header", "Ipi", "optional", "SMP only."),
 "kernel/include/kernel_arch_interface.h": ("Declares the arch functions that the kernel calls (arch_*): the C signature list of the world.", "header", "Platform (signatures)", "core", "the text form of the contract below the kernel."),
 "kernel/include/kernel_internal.h": ("Declares kernel-internal functions and gives inline helpers (swap return value) and init macros.", "header", "Scheduler (return value) + Boot", "core", "used by all objects."),
 "kernel/include/kernel_offsets.h": ("Generates the offsets of kernel structures for assembly code.", "header (build time)", "Platform (asm view of _kernel)", "core", "no run-time code; it is the layout contract between _kernel and the arch assembly."),
 "kernel/include/kernel_tls.h": ("Gives inline helpers for the thread-local storage area.", "header", "ThreadLife (TLS)", "optional", "CONFIG_THREAD_LOCAL_STORAGE."),
 "kernel/include/ksched.h": ("Gives the scheduler API of the objects as inline code: priority compare, unpend, z_sched_wake().", "header", "Scheduler", "core", "each object wake goes through it."),
 "kernel/include/kspinlock.h": ("Gives the scheduler spinlock helpers and the macros LOCK_SCHED_SPINLOCK and Z_SCHED_SPINLOCK.", "header", "Scheduler (lock)", "core", "the lock discipline of the scheduler."),
 "kernel/include/kswap.h": ("Gives the context switch as inline code: z_swap(), do_swap(), z_swap_irqlock().", "header", "Scheduler (switch)", "core", "each blocking call ends in it."),
 "kernel/include/kthread.h": ("Gives the thread state bits, the state predicates and should_preempt() as inline code.", "header", "Scheduler (states, selection rule)", "core", "the selection rule is here."),
 "kernel/include/metairq.h": ("Gives the meta-IRQ preemption bookkeeping as inline code.", "header", "Scheduler (meta-IRQ)", "optional", "active only with CONFIG_NUM_METAIRQ_PRIORITIES > 0."),
 "kernel/include/mmu.h": ("Gives page frame helpers for mmu.c.", "header", "-", "out", "no MMU on the lab boards."),
 "kernel/include/offsets_short.h": ("Gives short names of the generated offsets for assembly code.", "header (build time)", "Platform (asm view of _kernel)", "core", "no run-time code; see kernel_offsets.h."),
 "kernel/include/priority_q.h": ("Gives the priority queue backends (simple list, red-black tree, multi-queue) of the run queue and the wait queues as inline code.", "header", "RunQueue + WaitQueue", "core", "each ready and pend operation uses one backend."),
 "kernel/include/run_q.h": ("Gives the run queue operations (add, remove, best, yield) and the choice of the queue for each CPU as inline code.", "header", "RunQueue", "core", "the scheduler reaches the run queue only through it."),
 "kernel/include/scheduler.h": ("Declares the scheduler API of the objects (wake, wait, walk) and gives z_sched_wake_all().", "header", "Scheduler", "core", "object API of the scheduler contract."),
 "kernel/include/timeout_q.h": ("Gives the thread timeout helpers (add, abort, init) on top of timeout.c.", "header", "Timeout", "core", "the scheduler reaches timeout.c through it."),
 "kernel/include/timeslicing.h": ("Declares the time slice functions.", "header", "TimeSlice", "optional", "declarations only."),
 "kernel/include/usage.h": ("Gives the usage hook of the context switch.", "header", "Usage (hook)", "optional", "CONFIG_SCHED_THREAD_USAGE."),
 "kernel/include/wait_q.h": ("Gives the wait queue init and head access.", "header", "WaitQueue", "core", "each object has a wait queue."),
 "kernel/timeout_bucket.h": ("Gives the bucket backend of the timeout queue.", "CONFIG_TIMEOUT_BACKEND_BUCKET", "TimeoutQueue", "optional", "experimental backend."),
 "kernel/timeout_list.h": ("Gives the sorted delta-list backend of the timeout queue.", "CONFIG_TIMEOUT_BACKEND_DLIST (default)", "TimeoutQueue", "core", "default backend."),
 "kernel/timeout_minheap.h": ("Gives the min-heap backend of the timeout queue.", "CONFIG_TIMEOUT_BACKEND_MINHEAP", "TimeoutQueue", "optional", "experimental backend."),
 "kernel/timeout_wheel.h": ("Gives the timer wheel backend of the timeout queue.", "CONFIG_TIMEOUT_BACKEND_WHEEL", "TimeoutQueue", "optional", "experimental backend; the latency study compares it with DLIST."),
 "drivers/timer/sys_clock_init.c": ("Gives weak no-op defaults of the optional driver functions.", "always (with the timer drivers)", "SysClock", "core", "linked into each build."),
 "drivers/timer/system_timer_generic.h": ("Gives the generic tickless timer core: the tick accounting and the sys_clock_* functions on top of the driver primitives.", "included by 15 drivers, cortex_m_systick.c among them", "SysClock", "core", "the SysTick driver of G474RE and RT1060 uses it."),
 "drivers/timer/cortex_m_systick.c": ("Gives the SysTick primitives and ISR on the generic timer core, with an optional low-power companion.", "CONFIG_CORTEX_M_SYSTICK", "SysClock", "core", "default system timer of G474RE and RT1060."),
 "drivers/timer/nrf_grtc_timer.c": ("Gives the system timer on the nRF GRTC.", "CONFIG_NRF_GRTC_TIMER", "SysClock", "core", "default system timer of nRF54L15 (SysTick is off there by default)."),
 "drivers/timer/mcux_gpt_timer.c": ("Gives the system timer on the i.MX RT GPT.", "CONFIG_MCUX_GPT_TIMER (default y only with CONFIG_PM)", "SysClock", "optional", "RT1060 uses it only with power management."),
 "drivers/timer/stm32_lptim_timer.c": ("Gives the system timer on the STM32 LPTIM.", "CONFIG_STM32_LPTIM_TIMER (default y only with CONFIG_PM on STM32G4)", "SysClock", "optional", "G474RE uses it only with power management."),
 "drivers/timer/sys_lpm_hooks_counter.c": ("Gives the low-power companion hooks of the SysTick driver on a counter device.", "CONFIG_SYSTEM_TIMER_LPM_COMPANION_COUNTER", "SysClock (LPM)", "optional", "only with a low-power companion counter."),
 "include/zephyr/drivers/timer/system_timer.h": ("Declares the system timer driver API and gives the inline sys_clock_announce().", "header", "SysClock (API text)", "core", "the text form of the driver contract."),
}

def _ste(x):
    x = re.sub(r";\s+(\S)", lambda m: ". " + m.group(1).upper(), x)
    return x[0].upper() + x[1:] if x and x[0].islower() and not x.startswith(("k_", "z_")) else x


T = {u: tuple(_ste(v) if i in (0, 4) else v for i, v in enumerate(t)) for u, t in T.items()}
# copy: a unit file of another commit that is not in T. A file with the
# same name in another directory, or a renamed timeout backend, takes
# the entry of T. Each other file gets the group "New" and stays in the
# graph, so that its edges show in the diff.
RENAMED = {}
for u in [u for u in U if u not in T]:
    base = u.rsplit("/", 1)[-1]
    cands = [t for t in T if t.rsplit("/", 1)[-1] in (base, "timeout_" + base)]
    if len(cands) == 1:
        T[u] = T[cands[0]]
        RENAMED[u] = cands[0]
    elif u.startswith("kernel/timeout/"):
        T[u] = T["kernel/timeout_list.h"]
        RENAMED[u] = "kernel/timeout_list.h (group only)"
    else:
        T[u] = ("New file.", "?", "New: " + u, "core", "not in the table of gen.py")
        RENAMED[u] = None

# Kernel-unit group of each file (for the group graph and the SCCs)
GROUP = {}
for u, t in T.items():
    grp = t[2]
    GROUP[u] = grp

# ---- edge cleaning ---------------------------------------------------------
DRIVERS = {u for u in U if u.startswith("drivers/") or u.startswith("include/zephyr/drivers")}


def clean_edges(u, d):
    """Return {target: {"names": [...], "via": str|None}} of kernel unit edges."""
    out = defaultdict(lambda: {"names": set(), "via": set()})
    for tgt, names in d["edges"].get("unit", {}).items():
        if tgt == u or tgt.startswith("?"):
            continue
        for n in names:
            if n == "arch_spin_relax" and tgt == "kernel/idle.c":
                out[tgt]["via"].add("weak arch_spin_relax() default (SMP spin)")
            out[tgt]["names"].add(n)
    for tgt, names in d["edges"].get("unit-via-inline", {}).items():
        if tgt == u or tgt.startswith("?"):
            continue
        for n in names:
            via, _, callee = n.partition("->")
            if via.startswith("k_spin_"):
                if tgt == "kernel/spinlock_validate.c":
                    out[tgt]["names"].add(callee)
                    out[tgt]["via"].add("spinlock.h with CONFIG_SPIN_VALIDATE")
                elif tgt == "kernel/idle.c":
                    out[tgt]["names"].add(callee)
                    out[tgt]["via"].add("spinlock.h (SMP spin): weak arch_spin_relax()")
                # sys_clock_cycle_get_32 via CONFIG_SPIN_LOCK_TIME_LIMIT: SysClock
                elif tgt in DRIVERS:
                    out["SysClock"]["names"].add(callee)
                    out["SysClock"]["via"].add("spinlock.h with CONFIG_SPIN_LOCK_TIME_LIMIT")
                continue
            out[tgt]["names"].add(callee)
            out[tgt]["via"].add(f"inline {via}()")
    for tgt, names in d.get("uses_unit_macros", {}).items():
        if tgt == u:
            continue
        if u in DRIVERS and tgt in DRIVERS and tgt != "include/zephyr/drivers/timer/system_timer.h" \
                and tgt != "drivers/timer/system_timer_generic.h":
            continue   # same macro name in two drivers: no relation
        for n in names:
            out[tgt]["names"].add(n + " (macro)")
    return {t: {"names": sorted(v["names"]), "via": sorted(v["via"]) or None}
            for t, v in sorted(out.items())}


SYSCLOCK_UNITS = {"drivers/timer/system_timer_generic.h", "drivers/timer/cortex_m_systick.c",
                  "drivers/timer/nrf_grtc_timer.c", "drivers/timer/mcux_gpt_timer.c",
                  "drivers/timer/stm32_lptim_timer.c", "drivers/timer/sys_clock_init.c"}


def classify_target(t):
    if t == "SysClock" or t in DRIVERS:
        return "driver"
    if t.startswith("kernel/include/") or t.startswith("kernel/timeout_"):
        return "kernel-header"
    return "kernel"


def names_of(d, cats):
    s = set()
    for c in cats:
        for v in d["edges"].get(c, {}).values():
            s.update(v)
    return sorted(s)


units_out = {}
file_graph = defaultdict(set)
for u, d in U.items():
    purpose, build, grp, cls, reason = T[u]
    edges = clean_edges(u, d)
    calls_below = []
    for tgt, e in edges.items():
        kind = classify_target(tgt)
        target = tgt
        if tgt in SYSCLOCK_UNITS and u not in DRIVERS:
            target = "SysClock (" + tgt + ")"
        entry = {"kind": kind, "unit": target, "names": e["names"]}
        if e["via"]:
            entry["via"] = e["via"]
        calls_below.append(entry)
        if tgt != "SysClock" and not (tgt == "kernel/idle.c" and set(e["names"]) <= {"arch_spin_relax"}):
            file_graph[u].add(tgt)
    arch = names_of(d, ["arch", "macro:arch"])
    arch_inl = names_of(d, ["arch-via-inline"])
    if arch or arch_inl:
        e = {"kind": "arch/world", "unit": "Platform", "names": arch}
        if arch_inl:
            e["via_inline"] = arch_inl
        calls_below.append(e)
    drv = names_of(d, ["driver", "macro:driver"])
    if drv:
        calls_below.append({"kind": "driver", "unit": "SysClock", "names": drv})
    cc = names_of(d, ["clock_control"])
    if cc:
        calls_below.append({"kind": "driver", "unit": "clock_control", "names": cc})
    libs = set()
    for c in ("lib", "macro:lib", "libc", "tracing", "macro:tracing", "soc", "macro:soc"):
        for t in d["edges"].get(c, {}):
            libs.add(t.split("/")[-1] if "/" in t else t)
    if libs:
        calls_below.append({"kind": "library", "unit": "lib/libc/headers",
                            "names": sorted(libs)})
    unres = names_of(d, ["unresolved"])
    if unres:
        calls_below.append({"kind": "unresolved", "unit": "?",
                            "names": unres,
                            "note": "function pointers, HAL (nrfx, STM32 LL, MCUX), generated list helpers, or regex noise"})
    # contract above
    callers_by_name = defaultdict(set)
    for cu, names in d["called_by_units"].items():
        if cu == u:
            continue
        for n in names:
            callers_by_name[n.replace(" (macro)", "")].add(cu)
    api = []
    for a in d["api"]:
        names = [a["api"]] + a["forms"]
        callers = set()
        for n in names:
            callers |= callers_by_name.get(n, set())
        alias = [f.get("alias_of") for f in d["gives"] if f["name"] in a["forms"] and f.get("alias_of")]
        e = {"api": a["api"]}
        if a["syscall"]:
            e["syscall"] = True
        if alias:
            e["alias_of"] = alias[0]
        static_inline = all(f.get("static_inline") for f in d["gives"] if f["name"] in a["forms"])
        if static_inline and u.endswith(".h"):
            e["inline"] = True
        if callers:
            e["called_by_units"] = sorted(callers)
        ext = {k: v for k, v in a["ext_files"].items() if v and k != "kernel"}
        if ext:
            e["other_files_using_it"] = ext
        api.append(e)
    # shared state
    state = {}
    if d["kernel_fields"]:
        state["_kernel"] = d["kernel_fields"]
    if d["cpu_fields"]:
        state["_current_cpu"] = d["cpu_fields"]
    if d["current"]:
        state["_current"] = True
    if d["own_vars"]:
        state["owns"] = d["own_vars"]
    ev = {k: v for k, v in d["ext_vars"].items() if not (k == "kernel/init.c" and v == ["_kernel"])}
    if ev:
        state["uses_globals_of"] = ev
    exists = {}
    if d["unit_test"]:
        exists["unit_test"] = sorted({"safety/" + "/".join(p.split("/")[:4]) for p in d["unit_test"]})
    if d["faked_in"]:
        exists["faked_by"] = sorted({"safety/" + k for k in d["faked_in"]})
    tl = defaultdict(set)
    for k, v in d["tla"].items():
        tl[k] |= set(v)
    src = (ZROOT / u).read_text(errors="replace")
    for n, mods in g["tla_tags"].items():
        if re.search(r"^[A-Za-z_][\w \t*]*[ \t*]" + n + r"\s*\([^;]*$", src, re.M):
            for m in mods:
                tl[m].add(n)
    if tl:
        exists["tla"] = {k: sorted(v) for k, v in sorted(tl.items())}
    if d["satisfies"]:
        exists["satisfies_in_file"] = d["satisfies"]
    via = sorted(set(d["req_via_api"]) - set(d["satisfies"]),
                 key=lambda s: [int(x) for x in s.split("-")[2:]])
    if via:
        exists["satisfies_via_api_doc"] = via
    units_out[u] = {
        "lines": d["lines"],
        "purpose": purpose,
        "build": build,
        "kconfig_refs": list(d["configs"])[:12],
        "contract_above": grp,
        "safety_class": cls,
        "class_reason": reason,
        "gives": api,
        "calls_below": calls_below,
        "state": state,
        "exists": exists,
    }

# ---- SCCs ------------------------------------------------------------------


def sccs(graph, nodes):
    index, low, onstack, stack, res = {}, {}, set(), [], []
    counter = [0]

    def strong(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        onstack.add(v)
        for w in graph.get(v, ()):
            if w not in nodes:
                continue
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in onstack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                onstack.discard(w)
                comp.append(w)
                if w == v:
                    break
            res.append(sorted(comp))
    import sys
    sys.setrecursionlimit(10000)
    for v in sorted(nodes):
        if v not in index:
            strong(v)
    return [c for c in res if len(c) > 1]


fg = file_graph
nodes = set(U)
file_sccs = sccs(fg, nodes)
# group graph (canonical contract names, units of class "out" left out)


def canon(grp):
    if grp.startswith("Platform"):
        return "Platform"
    if grp.startswith("SysClock"):
        return "SysClock"
    if grp.startswith("Scheduler"):
        return "Scheduler"
    if grp.startswith("RunQueue") or grp.startswith("WaitQueue"):
        return "Queues"
    if grp.startswith("TimeoutQueue"):
        return "TimeoutQueue"
    if grp.startswith("ThreadLife + SchedApi"):
        return "Thread"
    for p in ("SchedApi", "ThreadLife", "Userspace", "Fatal", "Timeout", "TimeSlice", "Ipi",
              "ObjRegistry", "Usage", "Boot", "Device", "Idle"):
        if grp.startswith(p):
            return p
    if grp.startswith("Object: "):
        return "Obj:" + grp[len("Object: "):].split(" ")[0]
    if grp.startswith("New: "):
        return "New"
    return "out"


CANON = {u: canon(GROUP[u]) for u in GROUP}
for u in units_out:
    units_out[u]["contract_group"] = CANON[u]
gg = defaultdict(set)
gwhy = defaultdict(set)
for u, ts in fg.items():
    if T[u][3] == "out":
        continue
    for t in ts:
        if t in CANON and T[t][3] != "out" and CANON[t] != CANON[u]:
            gg[CANON[u]].add(CANON[t])
            gwhy[(CANON[u], CANON[t])].add(f"{key(u)} -> {key(t)}")
group_sccs = sccs(gg, set(CANON.values()))
# pairwise cycles (2-cycles) of files
pairs = sorted({tuple(sorted((a, b))) for a, ts in fg.items() for b in ts if a in fg.get(b, ())})


def edge_names(a, b):
    for c in units_out[a]["calls_below"]:
        if c.get("unit") == b:
            return c["names"]
    return []


cyc = {"file_sccs": file_sccs, "group_sccs": group_sccs,
       "two_cycles": [{"a": a, "b": b, "a_calls_b": edge_names(a, b), "b_calls_a": edge_names(b, a)}
                      for a, b in pairs]}
json.dump(cyc, open(HERE / "cycles.json", "w"), indent=1)
json.dump({k: {t: sorted(gwhy[(k, t)]) for t in sorted(v)} for k, v in gg.items()}, open(HERE / "group_graph.json", "w"), indent=1)

header = {
    "schema": 1,
    "generated": "2026-10-28",
    "zephyr_tree": LABEL,
    "safety_tree": "safety @ tkaestner/tla-spec",
    "method": ("lexical: universal-ctags 6.2.1 for definitions, a regex pass over each function body "
               "for calls (all #if branches count, no preprocessor), git grep for the users outside the unit set. "
               "Scripts: claude/kernel-unit/unit-map/.work/{callgraph,enrich,gen}.py"),
    "limits": [
        "Calls through function pointers are not edges (timeout handlers, work handlers, k_timer callbacks, walk callbacks, syscall marshalling).",
        "Calls inside macros of the public headers are only partly followed. LOG, tracing and assert macros are left out.",
        "All #if branches count: an edge can exist only for some configurations. 'kconfig_refs' gives the options in the file.",
        "Inline functions of public headers (spinlock.h, kernel.h, irq.h) are followed three levels deep. Edges through k_spin_lock()/k_spin_unlock() are summarized in 'via'.",
        "The assembly of the arch code (swap_helper.S) is not parsed. Its uses of _kernel are in unit-map.md.",
        "other_files_using_it counts files in the zephyr tree by area that contain the name (calls, declarations and docs in code), not call sites.",
        "satisfies_via_api_doc maps an @satisfies tag in an API doc comment (kernel.h and other headers) to the unit that implements the function.",
    ],
    "safety_classes": {
        "core": "needed by every safety application on the lab boards",
        "optional": "a Kconfig feature or a kernel object, in scope when the application enables or uses it",
        "out": "out of scope for the safety case on the lab boards",
    },
}
doc = {"meta": header, "units": units_out}


class D(yaml.SafeDumper):
    pass


D.add_representer(str, lambda dumper, s: dumper.represent_scalar(
    "tag:yaml.org,2002:str", s, style='"' if (":" in s or s.startswith(("*", "?", "!", "&", "-", "@"))) else None))
with open(OUTDIR / "units.yaml", "w") as f:
    f.write("# Unit map of the Zephyr kernel and the system timer drivers.\n"
            "# One entry for each file. See unit-map.md for the layers and the contracts.\n")
    yaml.dump(doc, f, Dumper=D, sort_keys=False, width=100, allow_unicode=True)
print("units", len(units_out), "file sccs", len(file_sccs), "group sccs", len(group_sccs), "pairs", len(pairs))

# ---- layering after the proposed cuts ---------------------------------------
REGROUP = {"kernel/include/kthread.h": "ThreadState", "kernel/include/kspinlock.h": "SchedLock",
           "kernel/smp/smp.c": "Smp", "kernel/spinlock_validate.c": "Platform",
           "kernel/include/metairq.h": "Scheduler"}
L = {u: REGROUP.get(u, REGROUP.get(RENAMED.get(u) or "", CANON[u])) for u in CANON}  # copy: RENAMED
L = {u: {"ThreadLife": "Thread", "Smp": "Boot"}.get(g_, g_) for u, g_ in L.items()}
for u in units_out:
    units_out[u]["contract_group"] = L[u]
PLATFORM_NAMES = {"k_is_in_isr", "z_early_rand_get", "arch_spin_relax", "z_fatal_error",
                  "z_smp_global_lock", "z_smp_global_unlock", "z_smp_release_global_lock"}
HOOK = [  # (from, to, reason); "*" matches any group
    ("*", "Fatal", "panic: a sink event of Platform (k_panic/k_oops); Fatal itself sits above Thread"),
    ("Scheduler", "Thread", "halt and switch hooks (abort cleanup, dummy thread, stack sentinel, switched-out mark)"),
    ("Scheduler", "ThreadLife", "halt hook (thread monitor exit)"),
    ("Scheduler", "Userspace", "halt hook (memory domain exit, permissions, object uninit)"),
    ("Scheduler", "ObjRegistry", "halt hook (object core unlink)"),
    ("Scheduler", "Usage", "switch hook (usage accounting)"),
    ("Scheduler", "TimeSlice", "slice reset hook (z_time_slice_reset)"),
    ("Timeout", "TimeSlice", "announce hook (z_time_slice after each announce)"),
    ("Ipi", "TimeSlice", "IPI hook (z_time_slice in z_sched_ipi)"),
    ("Ipi", "Obj:Event", "IPI work items use k_event: a second unit in smp/ipi.c, above Event"),
    ("SysClock", "Timeout", "clock port given by Timeout: sys_clock_lock/unlock and announce"),
    ("Usage", "Thread", "usage.c API part (stats query) calls thread.c: a second unit in usage.c"),
    ("ThreadState", "Thread", "thread_schedule_new() in kthread.h is SchedApi code in a header"),
    ("*", "Obj:Poll", "poll hook (z_handle_obj_poll_events)"),
    ("*", "Userspace", "registration hook (k_object_init)"),
    ("*", "ObjRegistry", "registration hook (k_obj_core_init_and_link)"),
    ("*", "Smp", "global IRQ lock of SMP (irq_lock): a Platform lock"),
]
KEEP_FROM = {"Boot", "Smp"}   # boot code calls everything: it sits on top


def is_hook(a, b):
    if a in KEEP_FROM:
        return None
    for f, t, why in HOOK:
        if (f == "*" or f == a) and t == b:
            return why
    return None


lg = defaultdict(set)
removed = defaultdict(set)
for u, ts in fg.items():
    if T[u][3] == "out":
        continue
    for t in ts:
        if T[t][3] == "out" or L[t] == L[u]:
            continue
        names = set()
        for c in units_out[u]["calls_below"]:
            if c.get("unit") == t or c.get("unit", "").endswith("(" + t + ")"):
                names |= {n.replace(" (macro)", "") for n in c["names"]}
        if names and names <= PLATFORM_NAMES:
            removed[("Platform-like call", L[u], L[t])].add(f"{key(u)} -> {key(t)}: {sorted(names)}")
            continue
        why = is_hook(L[u], L[t])
        if why:
            removed[(why, L[u], L[t])].add(f"{key(u)} -> {key(t)}")
            continue
        lg[L[u]].add(L[t])
lsccs = sccs(lg, set(L.values()))
# levels: longest path to a sink
level = {}


def lev(n, seen=()):
    if n in level:
        return level[n]
    if n in seen:
        return 0
    v = 0
    for m in lg.get(n, ()):
        v = max(v, lev(m, seen + (n,)) + 1)
    level[n] = v
    return v


for n in set(L.values()):
    lev(n)
cyc["layered_sccs"] = lsccs
cyc["levels"] = {k: v for k, v in sorted(level.items(), key=lambda x: (x[1], x[0]))}
cyc["layered_edges"] = {k: sorted(v) for k, v in sorted(lg.items())}
doc["meta"]["layers"] = {"levels": cyc["levels"], "edges": cyc["layered_edges"],
                         "note": "contract groups after the cuts in cut_edges. Level 0 has no group below it."}
doc["meta"]["unit_files_not_in_table"] = {u: v for u, v in sorted(RENAMED.items())}
doc["meta"]["cut_edges"] = [{"reason": r, "from": a, "to": b, "files": sorted(f)} for (r, a, b), f in sorted(removed.items())]
cyc["cut_edges"] = [{"reason": r, "from": a, "to": b, "files": sorted(f)} for (r, a, b), f in sorted(removed.items())]
json.dump(cyc, open(HERE / "cycles.json", "w"), indent=1)
with open(OUTDIR / "units.yaml", "w") as f:
    f.write("# Unit map of the Zephyr kernel and the system timer drivers.\n"
            "# One entry for each file. See unit-map.md for the layers and the contracts.\n")
    yaml.dump(doc, f, Dumper=D, sort_keys=False, width=100, allow_unicode=True)
print("layered sccs", lsccs)
print("levels", cyc["levels"])
