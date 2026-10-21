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
	extra=()
	[ "$expected" = probes ] && extra=(-continue)

	start=$(date +%s.%N)
	(cd "$spec/mc" && java -XX:+UseParallelGC -DTLA-Library="$spec/lib:$spec/objects:$spec/trace" \
		-cp "$TLA2TOOLS" tlc2.TLC -workers auto -cleanup "${extra[@]}" \
		-metadir "$out/states/${module}_${config}" -config "$cfg" "$module.tla") > "$log" 2>&1
	end=$(date +%s.%N)
	secs=$(awk -v a="$start" -v b="$end" 'BEGIN { printf "%.1f s", b - a }')

	distinct=$(grep -oE '[0-9,]+ distinct states found' "$log" | tail -1 | cut -d' ' -f1)
	depth=$(grep -oE 'depth of the complete state graph search is [0-9]+' "$log" | grep -oE '[0-9]+$')
	violated=$(grep -oE '(Invariant|Temporal properties|Action property) [A-Za-z_0-9]* ?(is|were) violated' "$log" |
		sed -E 's/^(Invariant|Temporal properties|Action property) //; s/ ?(is|were) violated//' | sort -u | tr '\n' ' ')
	violated=${violated% }

	if grep -q 'No error has been found' "$log" && [ -z "$violated" ]; then
		result=pass
	elif [ -n "$violated" ]; then
		result="fail:${violated// /,}"
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
