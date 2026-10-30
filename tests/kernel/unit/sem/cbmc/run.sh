#!/usr/bin/env bash
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0
#
# Run the CBMC harness ksem_harness.c: z_impl_k_sem_give() against KSem!Give
# or z_impl_k_sem_take() against KSem!Take, for all inputs.
# PREDICATE UNDER REVIEW (see README.rst).
#
# Usage: run.sh <give|take> <poll|nopoll> <lp64|ilp32> <rtc|nortc> [SEM_C] [-- cbmc args]
#   run.sh all     all 16 configurations, one after the other
#
# give/take: the harness function (harness_give, harness_take).
# poll/nopoll: the autoconf.h of the scenario kernel.unit.sem.poll or
#   kernel.unit.sem. The script builds them once with twister (build only)
#   into $CBMC_BUILD (default: <repo>/build/cbmc-sem).
# lp64/ilp32: the data model of goto-cc (the host, or -m32).
# rtc/nortc: KSEM_RUNTIME_CHECKS=1 or 0 (the assumption on the start state).
# SEM_C: a copy of sem.c (a mutant). Default: zephyr/kernel/sem.c.
# CFLAGS (environment): extra goto-cc flags, for example -DKSEM_REACH.
# TAG (environment): a suffix of the output directory.
#
# Output: $CBMC_BUILD/out/<fn>-<poll>-<model>-<rtc>[-<mutant>][-<tag>]/cbmc.txt.
# Exit status: the exit status of cbmc (0: all properties hold, 10: a
# property fails).
#
# Run one CBMC at a time on a machine with little memory.

set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../../../.." && pwd)
WS=$(cd "$REPO/.." && pwd)
Z=${ZEPHYR_BASE:-$WS/zephyr}
B=${CBMC_BUILD:-$REPO/build/cbmc-sem}

if [[ ${1:-} == all ]]; then
	shift
	status=0
	for fn in give take; do for m in lp64 ilp32; do for c in poll nopoll; do for r in rtc nortc; do
		"$0" $fn $c $m $r "$@" || status=$?
	done; done; done; done
	exit $status
fi

fn=$1 cfg=$2 model=$3 rtc=$4
shift 4
sem_c=""
if [[ $# -gt 0 && $1 != "--" ]]; then
	sem_c=$(realpath "$1")
	shift
fi
if [[ $# -gt 0 && $1 == "--" ]]; then shift; fi

scenario=kernel.unit.sem
if [[ $cfg == poll ]]; then scenario=kernel.unit.sem.poll; fi
autoconf=$(find "$B/twister" -path "*/$scenario/zephyr/include/generated/zephyr/autoconf.h" 2>/dev/null | head -1 || true)
if [[ -z $autoconf ]]; then
	(cd "$WS" && "$Z/scripts/twister" -T "$REPO/tests/kernel/unit/sem" -p unit_testing \
		-x=ZEPHYR_MODULES="$REPO" -s kernel.unit.sem -s kernel.unit.sem.poll \
		--build-only -O "$B/twister" >/dev/null)
	autoconf=$(find "$B/twister" -path "*/$scenario/zephyr/include/generated/zephyr/autoconf.h" | head -1)
fi
gen=$(dirname "$(dirname "$autoconf")")

name=$fn-$cfg-$model-$rtc
if [[ -n $sem_c ]]; then name=$name-$(basename "$sem_c" .c); fi
if [[ -n ${TAG:-} ]]; then name=$name-$TAG; fi
out=$B/out/$name
mkdir -p "$out"

defs=(-DKERNEL_UNIT_FAKE_GROUP_arch=1 -DKERNEL_UNIT_FAKE_GROUP_fatal=1
      -DKERNEL_UNIT_FAKE_GROUP_kernel_internal=1 -DKERNEL_UNIT_FAKE_GROUP_sched=1
      -DK_HEAP_MEM_POOL_SIZE=0 -DZTEST_UNITTEST)
incs=(-I"$REPO"/tests/kernel/unit/common/include
      -I"$Z"/subsys/testsuite/ztest/include/zephyr
      -I"$Z"/subsys/testsuite/ztest/unittest/include
      -I"$Z"/subsys/testsuite/include/zephyr
      -I"$Z"/subsys/testsuite/ztest/include
      -I"$Z"/subsys/testsuite/include
      -I"$Z"/include/zephyr -I"$Z"/include -I"$Z"/.
      -imacros "$autoconf"
      -I"$gen")
[[ $rtc == rtc ]] && defs+=(-DKSEM_RUNTIME_CHECKS=1) || defs+=(-DKSEM_RUNTIME_CHECKS=0)
if [[ -n $sem_c ]]; then defs+=("-DSEM_C=\"$sem_c\""); fi
mflag=()
# ILP32: the host gcc on aarch64 has no -m32. goto-cc gets -m32 (ILP32
# widths), and ilp32-gcc.sh preprocesses with the 32-bit ARM gcc of the
# Zephyr SDK.
if [[ $model == ilp32 ]]; then mflag=(-m32 --native-compiler "$HERE"/ilp32-gcc.sh); fi

# shellcheck disable=SC2086
goto-cc "${mflag[@]}" "${defs[@]}" ${CFLAGS:-} "${incs[@]}" -I"$HERE" -c "$HERE"/ksem_harness.c \
	-o "$out"/harness.goto

set +e
cbmc "$out"/harness.goto --function harness_$fn \
	--bounds-check --pointer-check --signed-overflow-check --unsigned-overflow-check \
	--div-by-zero-check --pointer-primitive-check --unwind 20 --unwinding-assertions \
	"$@" >"$out"/cbmc.txt 2>&1
rc=$?
set -e
grep -E '^\[|VERIFICATION|Runtime decision procedure' "$out"/cbmc.txt | grep -v ': SUCCESS$' || true
echo "$name: rc=$rc ($(grep -c ': SUCCESS$' "$out"/cbmc.txt) properties SUCCESS)"
exit $rc
