#!/usr/bin/env bash
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0
#
# Run TLC on the models in mc/expected.txt and compare each result with
# the expected result.
#
# Usage: run_tlc.sh [<module>[:<config>] ...]
#   Without arguments, all lines of mc/expected.txt run. With arguments,
#   only the lines of these modules (or of these module:config pairs) run.
#
# Environment:
#   TLA2TOOLS  path of tla2tools.jar, required. The hash must be the hash
#              in tools/tla2tools.sha256.
#   TLC_OUT    output directory (default: <spec>/build). For each run:
#              <module>_<config>.log, and summary.md for all runs.
#
# Exit status: 0 if each result is as expected, 1 if not, 2 on a setup
# error.

set -u

spec=$(cd "$(dirname "$0")/.." && pwd)
: "${TLA2TOOLS:?set TLA2TOOLS to the path of tla2tools.jar}"
out=${TLC_OUT:-$spec/build}

want=$(cut -d' ' -f1 "$spec/tools/tla2tools.sha256")
have=$(sha256sum "$TLA2TOOLS" | cut -d' ' -f1)
if [ "$want" != "$have" ]; then
	echo "run_tlc: $TLA2TOOLS has the hash $have, expected $want" >&2
	exit 2
fi

mkdir -p "$out"
summary=$out/summary.md
{
	echo "| Model | Expected | Result | Violated | Distinct states | Depth | Time |"
	echo "|---|---|---|---|---|---|---|"
} > "$summary"

selected() {
	[ $# -eq 0 ] && return 0
	local arg
	for arg in "${SELECT[@]}"; do
		[ "$arg" = "$1" ] || [ "$arg" = "$1:$2" ] && return 0
	done
	return 1
}

SELECT=("$@")
status=0
runs=0

while read -r module config expected rest; do
	case "$module" in ''|'#'*) continue ;; esac
	if [ ${#SELECT[@]} -gt 0 ] && ! selected "$module" "$config"; then
		continue
	fi
	runs=$((runs + 1))

	cfg=$spec/mc/${module}_${config}.cfg
	log=$out/${module}_${config}.log

	# One worker: TLC with more than one worker can miss states and
	# violations (tlaplus issue #1445, open at the pinned revision).
	# -fp 0: a fixed fingerprint function. Without it, TLC selects one at
	# random, and a reported trace can differ from run to run.
	tlc() { # <config file> <log file>
		(cd "$spec/mc" && java -XX:+UseParallelGC -DTLA-Library="$spec/lib:$spec/objects:$spec/trace" \
			-cp "$TLA2TOOLS" tlc2.TLC -workers 1 -fp 0 -cleanup -noGenerateSpecTE \
			-metadir "$out/states/${module}_${config}" -config "$1" "$module.tla") > "$2" 2>&1
	}

	start=$(date +%s.%N)
	if [ "$expected" = probes ]; then
		# One run for each probe, without -continue: TLC stops at the first
		# (shortest) violation. With -continue, TLC writes a trace for each
		# state that violates a probe, and in a large model the log grows
		# without a useful limit.
		: > "$log"
		for inv in $(awk '/^INVARIANTS?/{f=1; next} /^[A-Z]+/{f=0} f && NF {print $1}' "$cfg"); do
			one=$out/${module}_${config}.$inv.cfg
			awk -v inv="$inv" '/^INVARIANTS?/{print "INVARIANT " inv; f=1; next}
				/^[A-Z]+/{f=0} !f' "$cfg" > "$one"
			tlc "$one" "$out/${module}_${config}.$inv.log"
			cat "$out/${module}_${config}.$inv.log" >> "$log"
			rm -f "$one" "$out/${module}_${config}.$inv.log"
		done
	else
		tlc "$cfg" "$log"
	fi
	end=$(date +%s.%N)
	secs=$(awk -v a="$start" -v b="$end" 'BEGIN { printf "%.1f s", b - a }')

	distinct=$(grep -oE '[0-9,]+ distinct states found' "$log" | tail -1 | cut -d' ' -f1)
	depth=$(grep -oE 'depth of the complete state graph search is [0-9]+' "$log" | grep -oE '[0-9]+$' | sort -n | tail -1)
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
		case "${distinct//,/}" in
		''|0) result=no-states ;;
		*) result=pass ;;
		esac
	elif [ -n "$violated" ]; then
		result="fail:${violated// /,}"
	elif grep -q 'The first argument of Assert evaluated to FALSE' "$log"; then
		# A failed example test (mc/<Module>Test.tla). The log has the name
		# of the test, the value got and the value wanted.
		result=fail:Assert
	else
		result=error
	fi

	if [ "$expected" = probes ]; then
		# Each invariant of the configuration must be violated.
		missing=""
		for inv in $(awk '/^INVARIANTS?/{f=1; next} /^[A-Z]+/{f=0} f && NF {print $1}' "$cfg"); do
			case " $violated " in *" $inv "*) ;; *) missing="$missing $inv" ;; esac
		done
		[ -z "$missing" ] && [ -n "$violated" ] && result=probes
		[ -n "$missing" ] && result="probes-not-reached:${missing# }"
	fi

	if [ "$result" = "$expected" ]; then
		verdict="as expected"
	else
		verdict="UNEXPECTED ($result)"
		status=1
	fi
	printf '%-14s %-10s expected %-24s -> %s\n' "$module" "$config" "$expected" "$verdict"
	echo "| ${module} ${config} | $expected | $verdict | ${violated:--} | ${distinct:-?} | ${depth:-?} | $secs |" >> "$summary"
done < "$spec/mc/expected.txt"

if [ "$runs" -eq 0 ]; then
	echo "run_tlc: no model selected" >&2
	exit 2
fi
exit $status
