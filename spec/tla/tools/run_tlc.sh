#!/usr/bin/env bash
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0
#
# Run TLC on the models in mc/expected.txt (or selftest/expected.txt) and
# compare each result with the expected result and the recorded counts.
#
# Usage: run_tlc.sh [<module>[:<config>] ...]
#   Without arguments, all lines of the expected file run. With arguments,
#   only the lines of these modules (or of these module:config pairs) run.
#
# Environment:
#   TLA2TOOLS  path of tla2tools.jar, required. The hash must be the hash
#              in tools/tla2tools.sha256.
#   TLC_SUITE  mc (default) or selftest: the directory with the models and
#              the expected.txt file.
#   TLC_OUT    output directory (default: <spec>/build/<suite>). For each
#              line: <module>_<config>.log. For all lines: summary.md and
#              results.tsv.
#   TLC_WORKERS  number of TLC workers in one TLC process (default: 1).
#              Only 1 gives evidence: see the comment at the TLC command.
#   TLC_JOBS   number of TLC processes that run at the same time
#              (default: 1). Each process has its own -metadir and its
#              own java.io.tmpdir.
#   TLC_HEAP   Java heap of a line without heap= (for example 2g). Empty
#              (default): no -Xmx, the Java default or JAVA_TOOL_OPTIONS
#              applies. With TLC_JOBS > 1, the default is 2g.
#   TLC_MEM_BUDGET  with TLC_JOBS > 1: the sum of the heaps of the lines
#              that run at the same time (default: 16g). A line starts
#              only if its heap fits in the rest of the budget, or if no
#              other line runs.
#
# The fields of a line of the expected file:
#
#   <module> <config> <expected> [<key>=<value> ...]
#
# The keys (each one is optional):
#   states=<n>   distinct states. A different count fails the line.
#   depth=<n>    depth of the state graph. A different depth fails the line.
#   trace=<n>    number of states in the error trace (the last "State <n>:").
#   lasso=<n>    the state of "Back to state <n>" of a liveness trace, or
#                "stutter" for a trace that ends in stuttering.
#   heap=<size>  Java heap of this line (-Xmx), for example 4g.
#   repeat=<n>   run the line n times. Each run must give the same distinct
#                states and depth, or the result is "irreproducible".
#
# Exit status: 0 if each result is as expected, 1 if not, 2 on a setup
# error.

set -u

spec=$(cd "$(dirname "$0")/.." && pwd)
: "${TLA2TOOLS:?set TLA2TOOLS to the path of tla2tools.jar}"
suite=${TLC_SUITE:-mc}
case "$suite" in mc|selftest) ;; *) echo "run_tlc: TLC_SUITE must be mc or selftest" >&2; exit 2 ;; esac
dir=$spec/$suite
out=${TLC_OUT:-$spec/build/$suite}
workers=${TLC_WORKERS:-1}
jobs=${TLC_JOBS:-1}
heap_default=${TLC_HEAP:-}
[ "$jobs" -gt 1 ] && [ -z "$heap_default" ] && heap_default=2g
budget=${TLC_MEM_BUDGET:-16g}

want=$(cut -d' ' -f1 "$spec/tools/tla2tools.sha256")
have=$(sha256sum "$TLA2TOOLS" | cut -d' ' -f1)
if [ "$want" != "$have" ]; then
	echo "run_tlc: $TLA2TOOLS has the hash $have, expected $want" >&2
	exit 2
fi
if [ "$workers" != 1 ]; then
	echo "run_tlc: TLC_WORKERS=$workers: the results are not evidence (tlaplus issue #1445)" >&2
fi

mb() { # <size like 2g or 512m> -> megabytes
	case "$1" in
	*[gG]) echo $(( ${1%?} * 1024 )) ;;
	*[mM]) echo $(( ${1%?} )) ;;
	*) return 1 ;;
	esac
}
mb "$budget" > /dev/null || { echo "run_tlc: TLC_MEM_BUDGET must be like 16g" >&2; exit 2; }

# Read the selected lines of the expected file.
SELECT=("$@")
selected() {
	[ ${#SELECT[@]} -eq 0 ] && return 0
	local arg
	for arg in "${SELECT[@]}"; do
		[ "$arg" = "$1" ] || [ "$arg" = "$1:$2" ] && return 0
	done
	return 1
}
L_MOD=() L_CFG=() L_EXP=() L_REST=()
while read -r module config expected rest; do
	case "$module" in ''|'#'*) continue ;; esac
	selected "$module" "$config" || continue
	for kv in $rest; do
		case "$kv" in
		states=[0-9]*|depth=[0-9]*|trace=[0-9]*|lasso=[0-9]*|lasso=stutter|repeat=[0-9]*) ;;
		heap=*) mb "${kv#heap=}" > /dev/null || { echo "run_tlc: $module $config: bad $kv" >&2; exit 2; } ;;
		*) echo "run_tlc: $module $config: unknown field $kv" >&2; exit 2 ;;
		esac
	done
	L_MOD+=("$module") L_CFG+=("$config") L_EXP+=("$expected") L_REST+=("$rest")
done < "$dir/expected.txt"

if [ ${#L_MOD[@]} -eq 0 ]; then
	echo "run_tlc: no model selected" >&2
	exit 2
fi

mkdir -p "$out/rows"
rm -f "${out:?}"/rows/*

field() { # <rest> <key> -> value
	local kv
	for kv in $1; do
		case "$kv" in "$2="*) echo "${kv#*=}"; return ;; esac
	done
}

# Run one line. Write the result row to $out/rows/<index>.tsv and print
# the result line.
run_line() { # <index>
	local i=$1
	local module=${L_MOD[$i]} config=${L_CFG[$i]} expected=${L_EXP[$i]} rest=${L_REST[$i]}
	local name=${module}_${config}
	local cfg=$dir/${name}.cfg
	local log=$out/${name}.log
	local heap repeat
	heap=$(field "$rest" heap)
	heap=${heap:-$heap_default}
	repeat=$(field "$rest" repeat)
	repeat=${repeat:-1}

	# One worker by default: TLC with more than one worker can miss states
	# and violations (tlaplus issue #1445, fixed after the pinned revision).
	# Only runs with one worker are evidence (tools/TOOLS.rst).
	# -fp 0: a fixed fingerprint function. Without it, TLC selects one at
	# random, and a reported trace can differ from run to run.
	# Each process has its own -metadir and java.io.tmpdir, so processes
	# that run at the same time share no files except the jar and the
	# modules, which they only read.
	tlc() { # <config file> <log file> <state directory>
		local tmp=$out/tmp/${3##*/}
		mkdir -p "$tmp"
		(cd "$dir" && java -XX:+UseParallelGC ${heap:+-Xmx$heap} -Djava.io.tmpdir="$tmp" \
			-DTLA-Library="$spec/lib:$spec/objects:$spec/trace" \
			-cp "$TLA2TOOLS" tlc2.TLC -workers "$workers" -fp 0 -cleanup -noGenerateSpecTE \
			-metadir "$3" -config "$1" "$module.tla") > "$2" 2>&1
		rm -rf "${3:?}" "${tmp:?}"
	}

	local start end secs r
	start=$(date +%s.%N)
	if [ "$expected" = probes ]; then
		# One run for each probe, without -continue: TLC stops at the first
		# (shortest) violation. With -continue, TLC writes a trace for each
		# state that violates a probe, and in a large model the log grows
		# without a useful limit.
		: > "$log"
		local inv one
		for inv in $(awk '/^INVARIANTS?/{f=1; next} /^[A-Z]+/{f=0} f && NF {print $1}' "$cfg"); do
			one=$out/${name}.$inv.cfg
			awk -v inv="$inv" '/^INVARIANTS?/{print "INVARIANT " inv; f=1; next}
				/^[A-Z]+/{f=0} !f' "$cfg" > "$one"
			tlc "$one" "$out/${name}.$inv.log" "$out/states/$name"
			cat "$out/${name}.$inv.log" >> "$log"
			rm -f "$one" "$out/${name}.$inv.log"
		done
	else
		tlc "$cfg" "$log" "$out/states/$name"
		for ((r = 2; r <= repeat; r++)); do
			tlc "$cfg" "$out/${name}.r$r.log" "$out/states/$name.r$r"
		done
	fi
	end=$(date +%s.%N)
	secs=$(awk -v a="$start" -v b="$end" 'BEGIN { printf "%.1f", b - a }')

	count() { # <log> -> "<distinct> <depth>"
		local d p
		d=$(grep -oE '[0-9,]+ distinct states found' "$1" | tail -1 | cut -d' ' -f1)
		p=$(grep -oE 'depth of the complete state graph search is [0-9]+' "$1" | grep -oE '[0-9]+$' | sort -n | tail -1)
		echo "${d//,/} $p"
	}
	local distinct depth trace lasso calc actual violated result
	read -r distinct depth <<< "$(count "$log")"
	trace=$(grep -oE '^State [0-9]+:' "$log" | grep -oE '[0-9]+' | sort -n | tail -1)
	lasso=$(grep -oE '^Back to state [0-9]+' "$log" | grep -oE '[0-9]+$' | tail -1)
	grep -qE '^State [0-9]+: Stuttering' "$log" && lasso=stutter
	# The estimate of TLC that a fingerprint collision hid a state. TLC
	# prints it only for a run without an error.
	calc=$(grep -oE 'calculated \(optimistic\): +val = [-0-9.E]+' "$log" | tail -1 | grep -oE '[-0-9.E]+$')
	actual=$(grep -oE 'based on the actual fingerprints: +val = [-0-9.E]+' "$log" | tail -1 | grep -oE '[-0-9.E]+$')

	# A property that is an alias of an instance definition (Prop_X == WQ!X)
	# has the name of that definition in the TLC output: WQ!X. TLC 1.8.0
	# names one violated temporal property ("Temporal property X was
	# violated"). For more than one, it writes "Temporal properties were
	# violated", without a name.
	violated=$(grep -oE '(Invariant|Temporal propert(y|ies)|Action property) [A-Za-z_0-9!]* ?(is|was|were) violated' "$log" |
		sed -E 's/^(Invariant|Temporal propert(y|ies)|Action property) //; s/ ?(is|was|were) violated//; /^$/d' |
		sort -u | tr '\n' ' ')
	violated=${violated% }

	# TLC reports "No error has been found" also for a model without an
	# initial state (tlaplus issue #1475). Such a run checks nothing.
	if grep -q 'No error has been found' "$log" && [ -z "$violated" ]; then
		case "$distinct" in
		''|0) result=no-states ;;
		*) result=pass ;;
		esac
	elif [ -n "$violated" ]; then
		result="fail:${violated// /,}"
	elif grep -qE '^Error: Assumption .* is false' "$log"; then
		result=fail:Assume
	elif grep -q 'The first argument of Assert evaluated to FALSE' "$log"; then
		# A failed example test (mc/<Module>Test.tla). The log has the name
		# of the test, the value got and the value wanted.
		result=fail:Assert
	else
		result=error
	fi

	if [ "$expected" = probes ]; then
		# Each invariant of the configuration must be violated.
		local missing=""
		for inv in $(awk '/^INVARIANTS?/{f=1; next} /^[A-Z]+/{f=0} f && NF {print $1}' "$cfg"); do
			case " $violated " in *" $inv "*) ;; *) missing="$missing $inv" ;; esac
		done
		[ -z "$missing" ] && [ -n "$violated" ] && result=probes
		[ -n "$missing" ] && result="probes-not-reached:${missing# }"
	fi

	# Each repeated run must give the counts of the first run.
	for ((r = 2; r <= repeat; r++)); do
		if [ "$(count "$out/${name}.r$r.log")" != "$distinct $depth" ]; then
			result="irreproducible:run$r"
		fi
	done

	# The recorded counts. A difference is an unexpected result: the
	# state space changed, or the tool changed.
	local diffs="" key want got
	for key in states depth trace lasso; do
		want=$(field "$rest" "$key")
		[ -n "$want" ] || continue
		case $key in states) got=$distinct ;; depth) got=$depth ;; trace) got=$trace ;; lasso) got=$lasso ;; esac
		[ "$want" = "${got:-?}" ] || diffs="$diffs, $key ${got:-?} not $want"
	done

	local verdict
	if [ "$result" = "$expected" ] && [ -z "$diffs" ]; then
		verdict="as expected"
	elif [ "$result" = "$expected" ]; then
		verdict="UNEXPECTED (${diffs#, })"
	else
		verdict="UNEXPECTED ($result$diffs)"
	fi
	printf '%-14s %-10s expected %-24s -> %s\n' "$module" "$config" "$expected" "$verdict"
	local row
	row=$(printf '%s\t' "$module" "$config" "$expected" "$result" "$verdict" "${violated:--}" \
		"${distinct:-?}" "${depth:-?}" "${trace:--}" "${lasso:--}" "${calc:--}" "${actual:--}" \
		"$secs" "$workers")
	printf '%s%s\n' "$row" "${heap:--}" > "$out/rows/$i.tsv"
}

# The order of the start. With more than one process, the lines with the
# most recorded states start first, so the long lines do not wait at the
# end.
order=()
if [ "$jobs" -gt 1 ]; then
	while read -r _ i; do order+=("$i"); done < <(
		for i in "${!L_MOD[@]}"; do
			echo "$(field "${L_REST[$i]}" states) $i"
		done | awk '{ if (NF == 1) print 0, $1; else print }' | sort -s -k1,1nr)
else
	order=("${!L_MOD[@]}")
fi

declare -A RUNNING=() # pid -> heap in MB
used=0
limit=$(mb "$budget")
for i in "${order[@]}"; do
	if [ "$jobs" -le 1 ]; then
		run_line "$i"
		continue
	fi
	h=$(field "${L_REST[$i]}" heap)
	need=$(mb "${h:-$heap_default}")
	# Wait for a free slot and for the memory of the line.
	while [ ${#RUNNING[@]} -ge "$jobs" ] ||
		{ [ ${#RUNNING[@]} -gt 0 ] && [ $((used + need)) -gt "$limit" ]; }; do
		wait -n -p done_pid
		used=$((used - RUNNING[$done_pid]))
		unset "RUNNING[$done_pid]"
	done
	run_line "$i" &
	RUNNING[$!]=$need
	used=$((used + need))
done
wait

# results.tsv and summary.md in the order of the expected file.
status=0
{
	printf 'module\tconfig\texpected\tresult\tverdict\tviolated\tdistinct\tdepth\ttrace\tlasso\t'
	printf 'collision_calculated\tcollision_actual\tseconds\tworkers\theap\n'
	for i in "${!L_MOD[@]}"; do
		if [ -f "$out/rows/$i.tsv" ]; then
			cat "$out/rows/$i.tsv"
		else
			printf '%s\t%s\t%s\tmissing\tUNEXPECTED (no result)\t-\t?\t?\t-\t-\t-\t-\t0\t%s\t-\n' \
				"${L_MOD[$i]}" "${L_CFG[$i]}" "${L_EXP[$i]}" "$workers"
		fi
	done
} > "$out/results.tsv"
rm -rf "${out:?}/rows" "${out:?}/states" "${out:?}/tmp"
{
	echo "| Model | Expected | Result | Violated | Distinct states | Depth | Trace | Collision (calc. / actual) | Time | Workers |"
	echo "|---|---|---|---|---|---|---|---|---|---|"
	tail -n +2 "$out/results.tsv" | while IFS=$'\t' read -r m c e _ v vi d p t l ca ac s w _; do
		tr=$t
		[ "$l" != - ] && tr="$t (lasso $l)"
		echo "| $m $c | $e | $v | $vi | $d | $p | $tr | $ca / $ac | $s s | $w |"
	done
} > "$out/summary.md"
grep -q $'\tUNEXPECTED' "$out/results.tsv" && status=1
exit $status
