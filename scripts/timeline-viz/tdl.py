#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Compile TDL timing diagrams into the scenario model of render.js.

Usage:
  tdl.py compile <file.tdl>... [-I <dir>]... [-o out.json]

The output is {"lanes": {...}, "laneKeys": [...], "cards": [scenario, ...]}.
An "include" statement looks for the context file next to the diagram
first, then in each -I directory, then in contexts/ of this tool.
See README.md for the language.
"""
import argparse
import json
import re
import shlex
import sys
from pathlib import Path

CONTEXTS = Path(__file__).resolve().parent / "contexts"
KIND_WORDS = {"device": "dev", "tick": "tick", "switch": "sw", "thread": "thr", "hardware": "hw", "mask": "mask"}
STYLES = {"run": "run", "sleep": "wfi", "pending": "pending", "miss": "miss"}
EVENT_KINDS = {"edge", "tick", "stamp", "ref", "anchor"}
NAME = r"[A-Za-z_]\w*"
TIME = rf"(?:-?\d+|{NAME}(?:[+-]\d+)?)"
RE_DUR = re.compile(r"^(\d+)([!?]*)$")
RE_SPAN = re.compile(rf"^({TIME})\.\.({TIME})?([!?]*)$")


class TdlError(Exception):
    pass


def logical_lines(path):
    """Yield (line number, text) with comments removed and continuations joined."""
    out = []
    for no, raw in enumerate(Path(path).read_text().splitlines(), 1):
        text = strip_comment(raw)
        if not text.strip():
            continue
        if raw[:1] in (" ", "\t") and out:
            out[-1] = (out[-1][0], out[-1][1] + " " + text.strip())
        else:
            out.append((no, text.strip()))
    return out


def strip_comment(line):
    quoted = False
    for i, c in enumerate(line):
        if c == '"':
            quoted = not quoted
        elif c == "#" and not quoted and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def split_tip(text):
    """Split 'statement : tooltip' at the first ' : ' outside quotes."""
    quoted = False
    for i, c in enumerate(text):
        if c == '"':
            quoted = not quoted
        elif c == ":" and not quoted and i > 0 and text[i - 1] == " " and text[i + 1:i + 2] in (" ", ""):
            return text[:i].rstrip(), text[i + 1:].strip()
    return text, None


def parse_contexts(path, lanes):
    for no, text in logical_lines(path):
        tok = shlex.split(text)
        where = f"{path}:{no}"
        kind = None
        if "as" in tok:
            i = tok.index("as")
            if tok[i + 1] not in KIND_WORDS:
                raise TdlError(f"{where}: unknown kind '{tok[i + 1]}'")
            kind = KIND_WORDS[tok[i + 1]]
            tok = tok[:i]
        if tok[0] == "core" and len(tok) == 3:
            lanes[tok[1]] = {"label": tok[2], "kind": kind or ("mask" if tok[1] == "mask" else "hw"), "group": "core"}
        elif tok[0] in ("isr", "thread") and len(tok) == 4:
            prio = int(tok[2]) if re.fullmatch(r"-?\d+", tok[2]) else tok[2]
            if tok[0] == "isr" and not isinstance(prio, int) and prio not in ("ZLI", "low"):
                raise TdlError(f"{where}: an ISR priority is a number, ZLI or low")
            lanes[tok[1]] = {"label": tok[3], "kind": kind or ("dev" if tok[0] == "isr" else "thr"),
                             "group": "isr" if tok[0] == "isr" else "thr", "prio": prio}
        else:
            raise TdlError(f"{where}: expected 'core <id> \"label\"' or 'isr|thread <id> <prio> \"label\"'")


def find_include(name, here, include_path):
    """The path of the context file `name` (see the module doc)."""
    for d in (Path(here), *map(Path, include_path), CONTEXTS):
        if (d / name).is_file():
            return (d / name).resolve()
    return None


class Diagram:
    def __init__(self, path, lanes, include_path=()):
        self.path = path
        self.lanes = lanes
        self.include_path = include_path
        self.includes = []
        self.sc = {"id": None, "title": "", "segs": [], "events": [], "brackets": []}
        self.cursor = 0
        self.points = {}
        self.pieces = []
        self.piece = 0
        self.open_ends = []
        self.locks = []

    def err(self, no, msg):
        raise TdlError(f"{self.path}:{no}: {msg}")

    def time(self, no, expr):
        m = re.fullmatch(rf"({NAME})([+-]\d+)?", expr)
        if not m:
            return int(expr)
        if m.group(1) not in self.points:
            self.err(no, f"unknown time point '{m.group(1)}'")
        p, t = self.points[m.group(1)]
        if p != self.piece:
            self.err(no, f"time point '{m.group(1)}' is in another axis piece")
        return t + int(m.group(2) or 0)

    def statement(self, no, text):
        text, tip = split_tip(text)
        tok = shlex.split(text)
        head = tok[0]
        sc = self.sc
        if head == "include":
            found = find_include(tok[1], Path(self.path).parent, self.include_path)
            if not found:
                self.err(no, f"context file '{tok[1]}' not found")
            self.includes.append(found)
            parse_contexts(found, self.lanes)
        elif head == "diagram":
            sc["id"], sc["title"] = tok[1], tok[2]
        elif head == "letter":
            sc["letter"] = tok[1]
        elif head == "new":
            sc["isNew"] = True
        elif head == "num":
            sc.setdefault("nums", []).append([tok[1], tok[2]])
        elif head == "what":
            sc["what"] = tok[1]
        elif head == "evidence":
            sc.setdefault("evidence", []).append(tok[1])
        elif head == "src":
            sc["src"] = tok[1]
        elif head in ("axis", "piece"):
            m = RE_SPAN.fullmatch(tok[2])
            if not m or m.group(2) is None:
                self.err(no, "expected '<label> <from>..<to>'")
            frac = float(tok[3]) if len(tok) > 3 else None
            self.pieces.append({"from": int(m.group(1)), "to": int(m.group(2)), "frac": frac, "axis": tok[1]})
            self.piece = len(self.pieces) - 1
            self.cursor = int(m.group(1))
        elif head == "break":
            sc["breakLabel"] = tok[1]
        elif head == "prio":
            sc.setdefault("prio", {})[tok[1]] = int(tok[2]) if re.fullmatch(r"-?\d+", tok[2]) else tok[2]
        elif head == "at":
            self.cursor = self.time(no, tok[1])
        elif head.startswith("@"):
            self.point(no, head[1:], tok[1:])
        elif head == "span":
            m = RE_SPAN.fullmatch(tok[1])
            if not m or m.group(2) is None:
                self.err(no, "expected 'span <from>..<to>'")
            t0, t1 = self.time(no, m.group(1)), self.time(no, m.group(2))
            label = next((t for t in tok[2:] if t != "!"), str(t1 - t0))
            br = {"t0": t0, "t1": t1, "label": label, "m": "!" in tok[2:] or "!" in m.group(3)}
            if self.piece:
                br["p"] = self.piece
            sc["brackets"].append(br)
        elif head in self.lanes:
            self.step(no, head, tok[1:], tip)
        else:
            self.err(no, f"unknown statement or context '{head}'")

    def point(self, no, name, args):
        kind = "edge" if name == "edge" else "tick" if name.startswith("tick") else "stamp"
        label, t = name, self.cursor
        i, kind_set = 0, False
        while i < len(args):
            a = args[i]
            if a in EVENT_KINDS and not kind_set and i == 0:
                kind, kind_set = a, True
            elif a == "at":
                t = self.time(no, args[i + 1])
                i += 1
            else:
                label = a
            i += 1
        self.points[name] = (self.piece, t)
        if kind != "anchor":
            ev = {"t": t, "label": label, "kind": "stamp2" if kind == "ref" else kind}
            if self.piece:
                ev["p"] = self.piece
            self.sc["events"].append(ev)

    def step(self, no, lane, args, tip):
        style = "run"
        if args and args[0] in STYLES:
            style = STYLES[args.pop(0)]
        if not args:
            self.err(no, "a step needs a duration or a time range")
        when, rest = args[0], args[1:]
        label, lock = "", None
        for a in rest:
            if a.startswith("{") and a.endswith("}"):
                lock = a[1:-1]
                if lock not in ("basepri", "primask"):
                    self.err(no, f"unknown lock '{lock}'")
            else:
                label = a
        m = RE_DUR.fullmatch(when)
        open_end = False
        if m:
            t0 = self.cursor
            t1 = t0 + int(m.group(1))
            flags = m.group(2)
            self.cursor = t1
        else:
            m = RE_SPAN.fullmatch(when)
            if not m:
                self.err(no, f"'{when}' is not a duration or a time range")
            t0 = self.time(no, m.group(1))
            open_end = m.group(2) is None
            t1 = None if open_end else self.time(no, m.group(2))
            flags = m.group(3)
        if "?" in flags:
            style = "unk"
        seg = {"lane": lane, "t0": t0, "t1": t1, "s": "mask" if lane == "mask" else style, "label": label}
        if "!" in flags:
            seg["m"] = True
        if tip:
            seg["tip"] = tip
        if self.piece:
            seg["p"] = self.piece
        self.sc["segs"].append(seg)
        if open_end:
            self.open_ends.append((no, seg))
        if lock:
            self.locks.append((self.piece, lock, seg))

    def finish(self):
        sc = self.sc
        if not sc["id"]:
            raise TdlError(f"{self.path}: no 'diagram' statement")
        # an open end closes at the next step of the same context
        for no, seg in self.open_ends:
            later = [s["t0"] for s in sc["segs"] if s is not seg and s["lane"] == seg["lane"]
                     and s.get("p", 0) == seg.get("p", 0) and s["t0"] >= seg["t0"] and s["s"] != "pending"]
            if not later:
                self.err(no, f"the open end of '{seg['lane']}' has no later step")
            seg["t1"] = min(later)
        # lock attributes become mask segments; touching steps merge
        merged = []
        for p, lock, seg in sorted(self.locks, key=lambda x: (x[0], x[2]["t0"])):
            last = merged[-1] if merged else None
            if last and last["p"] == p and last["lock"] == lock and seg["t0"] <= last["t1"]:
                last["t1"] = max(last["t1"], seg["t1"])
            else:
                merged.append({"p": p, "lock": lock, "t0": seg["t0"], "t1": seg["t1"]})
        for mk in merged:
            seg = {"lane": "mask", "t0": mk["t0"], "t1": mk["t1"], "s": "mask", "label": mk["lock"].upper()}
            if mk["p"]:
                seg["p"] = mk["p"]
            sc["segs"].append(seg)
        # axis
        if len(self.pieces) == 1:
            pc = self.pieces[0]
            sc.update({"from": pc["from"], "to": pc["to"], "axis": pc["axis"]})
        elif self.pieces:
            free = [p for p in self.pieces if p["frac"] is None]
            rest = 1 - sum(p["frac"] for p in self.pieces if p["frac"] is not None)
            for p in free:
                p["frac"] = rest / len(free)
            sc["pieces"] = self.pieces
        else:
            raise TdlError(f"{self.path}: no 'axis' statement")
        # lanes in first-use order (the renderer sorts them)
        lanes = []
        for s in sc["segs"]:
            if s["lane"] not in lanes:
                lanes.append(s["lane"])
        sc["lanes"] = lanes
        return sc


def compile_file(path, lanes, include_path=(), includes=None):
    """Compile one diagram. `lanes` collects the contexts of all files.

    If `includes` is a list, the paths of the context files are added to it.
    """
    d = Diagram(path, lanes, include_path)
    for no, text in logical_lines(path):
        d.statement(no, text)
    if includes is not None:
        includes.extend(d.includes)
    return d.finish()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compile")
    c.add_argument("files", nargs="+")
    c.add_argument("-I", dest="include_path", action="append", default=[], metavar="DIR")
    c.add_argument("-o", "--out")
    args = ap.parse_args()
    lanes = {}
    try:
        cards = [compile_file(f, lanes, args.include_path) for f in args.files]
    except TdlError as e:
        sys.exit(f"error: {e}")
    out = json.dumps({"lanes": lanes, "laneKeys": list(lanes), "cards": cards}, ensure_ascii=False, indent=1)
    if args.out:
        Path(args.out).write_text(out)
    else:
        print(out)


if __name__ == "__main__":
    main()
