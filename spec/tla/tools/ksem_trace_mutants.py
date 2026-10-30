#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Run the code mutants of kernel/sem.c against the trace check of KSem.

For each mutant, the script writes a changed copy of zephyr/kernel/sem.c
(the zephyr tree does not change), builds a copy of the sem unit test app
that includes it, and runs the three trace scenarios with twister. Then it
cuts the traces and runs the trace check (check_traces.py) on each trace
that differs from the recorded trace of the original sem.c
(trace/ksem/). A trace that is the same has the same verdict.

A mutant is killed by the trace check if a verdict differs from the
expected verdict of trace/expected.txt (or a trace is missing or new). It
is killed by the unit tests if a test of a trace scenario fails (the unit
tests and the trace check run in the same binary).

Usage: ksem_trace_mutants.py [<mutant> ...]

Environment: TLA2TOOLS (see check_traces.py). The output is in
<repo>/build/trace-mutants/: results.json and results.md.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_traces as ct  # noqa: E402

SPEC = ct.SPEC
REPO = SPEC.parent.parent
WS = REPO.parent
ZEPHYR = WS / "zephyr"
APP = REPO / "tests" / "kernel" / "unit" / "sem"
OUT = REPO / "build" / "trace-mutants"

GIVE_LOCK = ("k_spinlock_key_t key = k_spin_lock(&sem_lock);\n\tbool resched;\n\n"
             "\tSYS_PORT_TRACING_OBJ_FUNC_ENTER(k_sem, give")
INC = "sem->count += (sem->count != sem->limit) ? 1U : 0U;"
ELSE = INC + "\n\t\tresched = sem_handle_poll_events(sem);"
GIVE_UNLOCK = "k_spin_unlock(&sem_lock, key);\n\t}\n\n\tSYS_PORT_TRACING_OBJ_FUNC_EXIT(k_sem, give"

# name -> (origin, [(old, new), ...]). origin "unit": the mutants of the unit
# tests (workspace notes, unit-tests/mutation/mutate_sem.py); "cbmc": the
# new give mutants of the CBMC route (cbmc/mutants.py).
MUTANTS = {
    "give_unlock_wrong_key": ("unit", [(GIVE_UNLOCK, "key.key++; " + GIVE_UNLOCK)]),
    "give_lt_instead_of_ne": ("unit", [("(sem->count != sem->limit)", "(sem->count < sem->limit)")]),
    "give_no_limit": ("unit", [("(sem->count != sem->limit) ? 1U : 0U", "1U")]),
    "give_poll_after_wake": ("unit", [("\t\tresched = true;\n\t} else {\n\t\tsem->count +=",
                                       "\t\tresched = true; (void)sem_handle_poll_events(sem);\n"
                                       "\t} else {\n\t\tsem->count +=")]),
    "give_wake_retval": ("unit", [("z_sched_wake(&sem->wait_q, 0, NULL)",
                                   "z_sched_wake(&sem->wait_q, -EAGAIN, NULL)")]),
    "give_always_unlock": ("unit", [("if (unlikely(resched)) {", "if (0) {")]),
    "take_busy_no_unlock": ("unit", [("\tif (K_TIMEOUT_EQ(timeout, K_NO_WAIT)) {\n"
                                      "\t\tk_spin_unlock(&sem_lock, key);",
                                      "\tif (K_TIMEOUT_EQ(timeout, K_NO_WAIT)) {\n")]),
    "take_ebusy_eagain": ("unit", [("ret = -EBUSY;", "ret = -EAGAIN;")]),
    "take_pend_forever": ("unit", [("&sem->wait_q, timeout);", "&sem->wait_q, K_FOREVER);")]),
    "take_unlock_then_pend": ("unit", [("ret = z_pend_curr(&sem_lock, key,",
                                        "k_spin_unlock(&sem_lock, key); "
                                        "ret = z_pend_curr(&sem_lock, key,")]),
    "take_isr_assert_removed": ("unit", [("__ASSERT(((arch_is_in_isr() == false) ||",
                                          "__ASSERT(((true) ||")]),
    "take_count_dec_outside_lock": ("unit", [(
        "\tk_spinlock_key_t key = k_spin_lock(&sem_lock);\n\n"
        "\tSYS_PORT_TRACING_OBJ_FUNC_ENTER(k_sem, take",
        "\tif (sem->count > 0U) { sem->count--; return 0; }\n"
        "\tk_spinlock_key_t key = k_spin_lock(&sem_lock);\n\n"
        "\tSYS_PORT_TRACING_OBJ_FUNC_ENTER(k_sem, take")]),
    "reset_wake_once": ("unit", [("while (z_sched_wake(&sem->wait_q, -EAGAIN, NULL)) {",
                                  "if (z_sched_wake(&sem->wait_q, -EAGAIN, NULL)) {")]),
    "reset_wake_zero": ("unit", [("z_sched_wake(&sem->wait_q, -EAGAIN, NULL)",
                                  "z_sched_wake(&sem->wait_q, 0, NULL)")]),
    "reset_short_circuit_poll": ("unit", [("resched = sem_handle_poll_events(sem) || resched;",
                                           "resched = resched || sem_handle_poll_events(sem);")]),
    "reset_count_kept": ("unit", [("\tsem->count = 0;\n", "\n")]),
    "reset_always_resched": ("unit", [("\tif (resched) {\n\t\tz_reschedule",
                                       "\tif (1) {\n\t\tz_reschedule")]),
    "init_no_limit_check": ("unit", [("CHECKIF(limit == 0U || initial_count > limit)",
                                      "CHECKIF(initial_count > limit)")]),
    "init_ge_check": ("unit", [("initial_count > limit)", "initial_count >= limit)")]),
    "init_no_waitq": ("unit", [("\tz_waitq_init(&sem->wait_q);\n", "\n")]),
    "init_no_poll_list": ("unit", [("\tsys_dlist_init(&sem->poll_events);\n", "\n")]),
    "poll_wrong_state": ("unit", [("K_POLL_STATE_SEM_AVAILABLE);\n#else",
                                   "K_POLL_STATE_NOT_READY);\n#else")]),
    "give_cap16": ("cbmc", [("(sem->count != sem->limit) ? 1U : 0U",
                             "(sem->count != sem->limit && sem->count != 0xFFFFU) ? 1U : 0U")]),
    "give_trunc16": ("cbmc", [(INC, "sem->count = (unsigned short)(sem->count + "
                                    "((sem->count != sem->limit) ? 1U : 0U));")]),
    "give_int_cmp": ("cbmc", [("(sem->count != sem->limit)", "((int)sem->count < (int)sem->limit)")]),
    "give_limit0_increments": ("cbmc", [("(sem->count != sem->limit)",
                                         "(sem->count != sem->limit || sem->limit == 0U)")]),
    "give_read_before_lock": ("cbmc", [(GIVE_LOCK, "unsigned int cnt = sem->count;\n\t" + GIVE_LOCK),
                                       (INC, "sem->count = cnt + ((cnt != sem->limit) ? 1U : 0U);")]),
    "give_count_after_unlock": ("cbmc", [(ELSE, "resched = false;"),
                                         (GIVE_UNLOCK, "k_spin_unlock(&sem_lock, key);\n\t\t" + INC +
                                          "\n\t\t(void)sem_handle_poll_events(sem);\n\t}\n\n"
                                          "\tSYS_PORT_TRACING_OBJ_FUNC_EXIT(k_sem, give")]),
    "give_poll_before_inc": ("cbmc", [(ELSE, "resched = sem_handle_poll_events(sem);\n\t\t" + INC)]),
    "give_wake_data": ("cbmc", [("z_sched_wake(&sem->wait_q, 0, NULL)",
                                 "z_sched_wake(&sem->wait_q, 0, sem)")]),
    "give_resched_count1": ("cbmc", [("resched = sem_handle_poll_events(sem);\n\t}\n\n\tif (unlikely",
                                      "resched = sem_handle_poll_events(sem) || sem->count == 1U;"
                                      "\n\t}\n\n\tif (unlikely")]),
}


def build_app(sem_c: Path) -> Path:
    app = OUT / "app"
    if app.exists():
        shutil.rmtree(app)
    shutil.copytree(APP, app)
    t = (app / "src" / "test_sem.c").read_text()
    (app / "src" / "test_sem.c").write_text(t.replace("#include <kernel/sem.c>",
                                                      '#include "mutant_sem.c"'))
    k = (app / "Kconfig").read_text()
    (app / "Kconfig").write_text(k.replace('rsource "../common/Kconfig"',
                                           f'source "{APP.parent / "common" / "Kconfig"}"'))
    shutil.copy(sem_c, app / "src" / "mutant_sem.c")
    return app


def run_twister(app: Path, out: Path):
    if out.exists():
        shutil.rmtree(out)
    cmd = [str(ZEPHYR / "scripts" / "twister"), "-T", str(app), "-p", "unit_testing",
           f"-x=ZEPHYR_MODULES={REPO}", "-j", "2", "-O", str(out)]
    for s in ct.SCENARIOS:
        cmd += ["-s", s]
    subprocess.run(cmd, cwd=WS, capture_output=True, text=True)
    report = out / "twister.json"
    if not report.exists():
        return {"error": "no twister report"}
    data = json.loads(report.read_text())
    res = {}
    for suite in data.get("testsuites", []):
        name = suite["name"].split("/")[-1]
        failed = [tc["identifier"].split(".")[-1] for tc in suite.get("testcases", [])
                  if tc.get("status") in ("failed", "error")]
        if suite.get("status") not in ("passed",) or failed:
            res[name] = failed or [suite.get("status", "?")]
    return res


def main() -> int:
    jar = os.environ.get("TLA2TOOLS")
    if not jar:
        print("set TLA2TOOLS", file=sys.stderr)
        return 2
    only = set(sys.argv[1:])
    expected = {}
    for line in ct.EXPECTED.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            c, t, v = line.split()[:3]
            expected[f"{c}/{t}"] = v
    src = (ZEPHYR / "kernel" / "sem.c").read_text()
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, (origin, edits) in MUTANTS.items():
        if only and name not in only:
            continue
        text = src
        for old, new in edits:
            if text.count(old) != 1:
                sys.exit(f"{name}: the pattern occurs {text.count(old)} times: {old!r}")
            text = text.replace(old, new)
        sem_c = OUT / "src" / f"{name}.c"
        sem_c.parent.mkdir(parents=True, exist_ok=True)
        sem_c.write_text(text)
        app = build_app(sem_c)
        tw = OUT / "twister" / name
        tests = run_twister(app, tw)
        traces = OUT / "traces" / name
        if traces.exists():
            shutil.rmtree(traces)
        ct.record(tw, traces)
        killed = {}
        new = {f"{p.parent.name}/{p.stem}": p for p in traces.glob("*/*.ndjson")}
        old = {f"{p.parent.name}/{p.stem}": p for p in ct.TRACES.glob("*/*.ndjson")}
        for key in sorted(set(new) | set(old)):
            if key not in new:
                killed[key] = "missing"
                continue
            if key not in old:
                killed[key] = "new"
                continue
            if new[key].read_text() == old[key].read_text():
                continue
            events = ct.load(new[key])
            if not any(e["ev"] == "call" for e in events):
                verdict = "empty"
            elif any(v > ct.INT_MAX for v in ct.ints(events)):
                verdict = "out-of-range"
            else:
                stem = f"{name}__{key.replace('/', '__')}"
                cfg = OUT / "tlc" / f"{stem}.cfg"
                cfg.parent.mkdir(parents=True, exist_ok=True)
                ct.write_cfg(new[key], events, cfg)
                verdict = ct.run_tlc(jar, cfg, OUT / "tlc" / f"{stem}.log",
                                     OUT / "tlc" / "states" / stem)
            if verdict != expected.get(key):
                killed[key] = verdict
        results[name] = {"origin": origin, "tests": tests, "trace": killed}
        print(f"{name} [{origin}]: unit tests {'KILLED' if tests else 'survived'}; "
              f"trace check {'KILLED (' + str(len(killed)) + ' traces)' if killed else 'survived'}",
              flush=True)
    (OUT / "results.json").write_text(json.dumps(results, indent=1))
    with (OUT / "results.md").open("w") as f:
        f.write("| Mutant | Origin | Unit tests (trace scenarios) | Trace check | Example |\n")
        f.write("|---|---|---|---|---|\n")
        for name, r in results.items():
            ex = next(iter(r["trace"].items()), ("", ""))
            f.write(f"| {name} | {r['origin']} | {'killed' if r['tests'] else 'survived'} | "
                    f"{'killed (' + str(len(r['trace'])) + ')' if r['trace'] else 'survived'} | "
                    f"{ex[0]} {ex[1]} |\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
