#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Compare the code of an ISR before its time stamp in two images.

    prestamp.py A.elf B.elf [--function resp_isr] [--objdump PREFIX-objdump] [--stamp '#36']

An option that adds code after the time stamp of an ISR (for example the
tail witnesses, LATBENCH_TAIL) must not change the code before it: that
code is on the latency path of the sample. The script disassembles the
function in both ELFs, takes the instructions up to the first load with
the offset of the timer counter (TIM2 CNT: [rN, #36] on nucleo_g474re),
and compares them. Register names and the offsets of literal loads are
masked: they do not change the time of an instruction. The size of each
instruction is kept (a 16-bit and a 32-bit form of an instruction can have
a different time).

Exit code 0: the same sequence. 1: different (the script prints both).
The comparison does not see the code placement effect: the same
instructions at other addresses can take other times in flash (see the
guide, explanation/code-placement).
"""

import argparse
import re
import subprocess
import sys

REG = re.compile(r"\b(r\d{1,2}|ip|lr|sp|fp|sl)\b")
LIT = re.compile(r"\[pc, #-?\d+\]")
COMMENT = re.compile(r"\s*[@;].*$")


def disassemble(elf, function, objdump):
    out = subprocess.run([objdump, "-d", f"--disassemble={function}", elf], capture_output=True, text=True,
                         check=True).stdout
    return parse(out)


def parse(text):
    """[(size in bytes, mnemonic, operands)] of the instructions of an objdump -d text."""
    out = []
    for line in text.splitlines():
        m = re.match(r"^\s*[0-9a-f]+:\t([0-9a-f ]+?)\s*\t(\S+)\s*(.*)$", line)
        if not m:
            continue
        raw = m.group(1).replace(" ", "")
        out.append((len(raw) // 2, m.group(2), COMMENT.sub("", m.group(3)).strip()))
    return out


def normal(insn):
    size, mnem, ops = insn
    ops = LIT.sub("[pc, #LIT]", ops)
    return size, mnem, REG.sub("R", ops)


def before_stamp(insns, stamp="#36"):
    """The instructions up to and with the first load of the counter ('ldr Rx, [Ry, #36]')."""
    out = []
    for i in insns:
        out.append(i)
        if i[1].startswith("ldr") and re.search(r"\[(r\d+|ip), " + re.escape(stamp) + r"\]", i[2]):
            return out
    return None


def compare(a, b, stamp="#36"):
    """(same, normalized a, normalized b) of the code before the stamp of two instruction lists."""
    pa, pb = before_stamp(a, stamp), before_stamp(b, stamp)
    if pa is None or pb is None:
        raise ValueError("no load of the counter in the function")
    na, nb = [normal(i) for i in pa], [normal(i) for i in pb]
    return na == nb, na, nb


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--function", default="resp_isr")
    ap.add_argument("--objdump", default="arm-zephyr-eabi-objdump")
    ap.add_argument("--stamp", default="#36", help="offset of the counter load (default #36: TIM2 CNT)")
    args = ap.parse_args()
    same, na, nb = compare(disassemble(args.a, args.function, args.objdump),
                           disassemble(args.b, args.function, args.objdump), args.stamp)
    print(f"{args.function}: {len(na)} and {len(nb)} instructions before the time stamp: "
          + ("the same" if same else "DIFFERENT"))
    if not same:
        for x, y in zip(na + [None] * (len(nb) - len(na)), nb + [None] * (len(na) - len(nb))):
            print(f"  {'' if x == y else '*'} {x}  |  {y}")
    sys.exit(0 if same else 1)


if __name__ == "__main__":
    main()
