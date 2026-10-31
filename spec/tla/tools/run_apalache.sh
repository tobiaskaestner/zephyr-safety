#!/usr/bin/env bash
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0
#
# Run Apalache on the lines of apalache/expected.txt and compare each
# result with the expected result. Research only: no Apalache result is
# evidence yet (tools/TOOLS.rst).
#
# Usage: run_apalache.sh [<module>[:<name>] ...]
#   Without arguments, all lines run. With arguments, only the lines of
#   these modules (or of these module:name pairs) run.
#
# Environment:
#   APALACHE_HOME  the unpacked release (default:
#                  ~/.cache/apalache/apalache-0.62.4). The hash of
#                  lib/apalache.jar must be the jar hash in
#                  tools/apalache.sha256.
#   APALACHE_TGZ   the archived release tarball (default: the archive
#                  copy /wrk/z/tla-archive/apalache/sha256-<hash>/). If the
#                  file exists, its hash must be the hash in
#                  tools/apalache.sha256.
#   APALACHE_OUT   output directory (default: <spec>/build/apalache). For
#                  each line: <module>_<name>.log. For all lines:
#                  results.tsv and summary.md.
#   APALACHE_HEAP  Java heap (default: 2g). The Z3 solver runs in the same
#                  process, outside the Java heap.
#   APALACHE_MEM   the memory limit of each run, Java heap and Z3 together
#                  (default: 3G). The run starts in a systemd scope with
#                  MemoryMax=<limit> and no swap, so a run that needs more
#                  memory stops ("killed"), and no other process of the host
#                  is stopped. "none": no limit (and no systemd scope).
#
# The runs are one at a time. Apalache and Z3 need much memory: do not run
# other TLC or Apalache processes at the same time on a small host.
#
# The fields of a line of the expected file:
#
#   <module> <name> <expected> [<key>=<value> ...]
#
# <module> is the name of a module in lib/, objects/, mc/ or apalache/.
# A name that starts with "typecheck" runs "apalache-mc typecheck" (key
# omit only). Each other name runs "apalache-mc check" with the keys:
#
#   init=<op>      the initial predicate (default Init)
#   next=<op>      the next-state relation (default Next)
#   inv=<op>       the invariant (required)
#   length=<n>     the number of steps (required)
#   cinit=<op>     the operator that gives the constants
#   timeout=<s>    stop the run after s seconds (default 1200)
#   omit=<M.D,...> remove the definitions D of the modules M from the copy
#                  of the specs before the run. Only for definitions that
#                  the checked formulas do not use and that Apalache does not
#                  accept (README.rst, "Apalache"). The copy is in
#                  <out>/src.
#
# Each check run has --no-deadlock: the lines check invariants only.
#
# The results:
#
#   pass             Apalache reports no error (EXITCODE: OK)
#   violated         the invariant is violated (exit code 12). The log has
#                    the path of the counterexample (violation1.tla).
#   fail:<code>      another exit code of Apalache: 120 is a type error,
#                    255 an input or configuration error (for example a
#                    missing type annotation)
#   timeout          the run took longer than its timeout
#   killed           the run reached the memory limit
#
# Exit status: 0 if each result is as expected, 1 if not, 2 on a setup
# error.

set -u

spec=$(cd "$(dirname "$0")/.." && pwd)
pins=$spec/tools/apalache.sha256
want_tgz=$(sed -n 1p "$pins" | cut -d' ' -f1)
want_jar=$(sed -n 2p "$pins" | cut -d' ' -f1)
home=${APALACHE_HOME:-$HOME/.cache/apalache/apalache-0.62.4}
tgz=${APALACHE_TGZ:-/wrk/z/tla-archive/apalache/sha256-$want_tgz/apalache-0.62.4.tgz}
out=${APALACHE_OUT:-$spec/build/apalache}
heap=${APALACHE_HEAP:-2g}
mem=${APALACHE_MEM:-3G}

# The identity of the tool: the jar that runs, and the archived release.
jar=$home/lib/apalache.jar
if [ ! -f "$jar" ]; then
	echo "run_apalache: no $jar (set APALACHE_HOME)" >&2
	exit 2
fi
have=$(sha256sum "$jar" | cut -d' ' -f1)
if [ "$have" != "$want_jar" ]; then
	echo "run_apalache: $jar has the hash $have, expected $want_jar" >&2
	exit 2
fi
if [ -f "$tgz" ]; then
	have=$(sha256sum "$tgz" | cut -d' ' -f1)
	if [ "$have" != "$want_tgz" ]; then
		echo "run_apalache: $tgz has the hash $have, expected $want_tgz" >&2
		exit 2
	fi
else
	echo "run_apalache: note: no archived release at $tgz, only the jar hash is checked" >&2
fi
if [ "$mem" != none ] && ! systemd-run --user --scope --quiet -p MemoryMax=64M true 2> /dev/null; then
	echo "run_apalache: systemd-run --user --scope does not work; set APALACHE_MEM=none" >&2
	exit 2
fi

SELECT=("$@")
selected() {
	[ ${#SELECT[@]} -eq 0 ] && return 0
	local arg
	for arg in "${SELECT[@]}"; do
		[ "$arg" = "$1" ] || [ "$arg" = "$1:$2" ] && return 0
	done
	return 1
}

field() { # <rest> <key> -> value
	local kv
	for kv in $1; do
		case "$kv" in "$2="*) echo "${kv#*=}"; return ;; esac
	done
}

L_MOD=() L_NAME=() L_EXP=() L_REST=()
while read -r module name expected rest; do
	case "$module" in ''|'#'*) continue ;; esac
	selected "$module" "$name" || continue
	for kv in $rest; do
		case "$kv" in
		init=*|next=*|inv=*|cinit=*|omit=*) ;;
		length=[0-9]*|timeout=[0-9]*) ;;
		*) echo "run_apalache: $module $name: unknown field $kv" >&2; exit 2 ;;
		esac
	done
	if [ "${name#typecheck}" = "$name" ]; then
		for key in inv length; do
			[ -n "$(field "$rest" $key)" ] || { echo "run_apalache: $module $name: no $key=" >&2; exit 2; }
		done
	fi
	L_MOD+=("$module") L_NAME+=("$name") L_EXP+=("$expected") L_REST+=("$rest")
done < "$spec/apalache/expected.txt"

if [ ${#L_MOD[@]} -eq 0 ]; then
	echo "run_apalache: no line selected" >&2
	exit 2
fi

mkdir -p "$out"
# The copy of the specs: one flat directory, as Apalache reads the
# modules of INSTANCE and EXTENDS from the directory of the root module.
copy_specs() { # <omit list>
	rm -rf "${out:?}/src"
	mkdir -p "$out/src"
	cp "$spec"/lib/*.tla "$spec"/objects/*.tla "$spec"/mc/*.tla "$spec"/apalache/*.tla "$out/src/"
	# lib/Apalache.tla is a copy of the standard module for TLC. Apalache
	# reads a module of the directory before its own, so remove the copy.
	rm -f "$out/src/Apalache.tla"
	local item m d
	for item in ${1//,/ }; do
		m=${item%%.*} d=${item#*.}
		[ -f "$out/src/$m.tla" ] || { echo "run_apalache: omit=$item: no module $m" >&2; return 1; }
		# Remove the definition from its head to the next blank line.
		awk -v d="$d" '
			$0 ~ "^" d "(\\(.*\\))? *==" { skip = 1 }
			skip && /^[ \t]*$/ { skip = 0 }
			!skip' "$out/src/$m.tla" > "$out/src/$m.tla.new"
		if cmp -s "$out/src/$m.tla" "$out/src/$m.tla.new"; then
			echo "run_apalache: omit=$item: no definition $d in $m" >&2
			return 1
		fi
		mv "$out/src/$m.tla.new" "$out/src/$m.tla"
	done
}

rows=()
status=0
for i in "${!L_MOD[@]}"; do
	module=${L_MOD[$i]} name=${L_NAME[$i]} expected=${L_EXP[$i]} rest=${L_REST[$i]}
	log=$out/${module}_${name}.log
	if ! copy_specs "$(field "$rest" omit)"; then
		exit 2
	fi
	if [ ! -f "$out/src/$module.tla" ]; then
		echo "run_apalache: no module $module" >&2
		exit 2
	fi
	args=()
	if [ "${name#typecheck}" != "$name" ]; then
		args=(typecheck)
		limit=600
	else
		args=(check --no-deadlock
			--init="$(field "$rest" init)" --next="$(field "$rest" next)"
			--inv="$(field "$rest" inv)" --length="$(field "$rest" length)")
		[ "${args[2]}" = --init= ] && args[2]=--init=Init
		[ "${args[3]}" = --next= ] && args[3]=--next=Next
		c=$(field "$rest" cinit)
		[ -n "$c" ] && args+=(--cinit="$c")
		limit=$(field "$rest" timeout)
		limit=${limit:-1200}
	fi
	run_dir=$out/runs/${module}_${name}
	rm -rf "$run_dir" "$out/tmp"
	mkdir -p "$run_dir" "$out/tmp"
	scope=()
	# The peak memory comes from GNU time, if the host has it (the lab host
	# has not; the summary then gives 0 MB).
	meter=()
	[ -x /usr/bin/time ] && meter=(/usr/bin/time -f '%M' -o "$out/tmp/maxrss")
	[ "$mem" != none ] && scope=(systemd-run --user --scope --quiet -p "MemoryMax=$mem" -p MemorySwapMax=0)
	# TMPDIR: the launcher writes its SANY files there (not to /tmp).
	start=$(date +%s.%N)
	(cd "$out/src" && "${meter[@]}" \
		"${scope[@]}" env TMPDIR="$out/tmp" JVM_ARGS="-Xmx$heap" \
		timeout "$limit" "$home/bin/apalache-mc" --out-dir="$run_dir" "${args[0]}" "${args[@]:1}" "$module.tla") \
		> "$log" 2>&1
	code=$?
	end=$(date +%s.%N)
	secs=$(awk -v a="$start" -v b="$end" 'BEGIN { printf "%.1f", b - a }')
	maxrss=$(tail -1 "$out/tmp/maxrss" 2> /dev/null | grep -oE '^[0-9]+$')
	mb=$(( ${maxrss:-0} / 1024 ))
	transitions=$(grep -oE 'Found [0-9]+ transitions' "$log" | grep -oE '[0-9]+' | tail -1)

	if grep -q 'EXITCODE: OK' "$log"; then
		result=pass
	elif grep -q 'EXITCODE: ERROR (12)' "$log"; then
		result=violated
	elif e=$(grep -oE 'EXITCODE: ERROR \([0-9]+\)' "$log" | grep -oE '[0-9]+'); then
		result=fail:$e
	elif [ $code -eq 124 ]; then
		result=timeout
	elif [ $code -eq 137 ] || [ $code -eq 143 ]; then
		result=killed
	else
		result=error:$code
	fi
	cti=$(grep -oE '/[^ ,]*violation1\.tla' "$log" | head -1)

	if [ "$result" = "$expected" ]; then
		verdict="as expected"
	else
		verdict="UNEXPECTED ($result)"
		status=1
	fi
	printf '%-12s %-22s expected %-10s -> %s (%s s, %s MB)\n' "$module" "$name" "$expected" "$verdict" "$secs" "$mb"
	rows+=("$(printf '%s\t' "$module" "$name" "$expected" "$result" "$verdict" "${transitions:--}" "$secs" "$mb")${cti:--}")
done
rm -rf "${out:?}/tmp"

{
	printf 'module\tname\texpected\tresult\tverdict\ttransitions\tseconds\tmax_rss_mb\tcounterexample\n'
	printf '%s\n' "${rows[@]}"
} > "$out/results.tsv"
{
	echo "| Line | Expected | Result | Transitions | Time | Max RSS |"
	echo "|---|---|---|---|---|---|"
	tail -n +2 "$out/results.tsv" | while IFS=$'\t' read -r m n e _ v t s r _; do
		echo "| $m $n | $e | $v | $t | $s s | $r MB |"
	done
} > "$out/summary.md"
exit $status
