# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""One self-contained HTML page with the study.json files of a results tree.

For each instance: the question, the notes, the acceptance and rebuild
checks, the hypotheses with each check, and the central results. No
plots, no scripts from other places; the same tree gives the same bytes.
"""

import html
import json

from . import layout

CSS = """
:root { --bg:#fff; --fg:#1d1d1f; --muted:#666; --line:#ddd; --ok:#1a7f37; --bad:#c62828; --open:#8a6d00; --card:#f6f7f9; }
@media (prefers-color-scheme: dark) { :root { --bg:#16181c; --fg:#e8e8e8; --muted:#a0a0a0; --line:#333;
  --ok:#5bd17a; --bad:#ff7b72; --open:#e3b341; --card:#1e2127; } }
body { background:var(--bg); color:var(--fg); font:14px/1.45 system-ui,sans-serif; margin:0 auto; max-width:1100px; padding:16px; }
h1 { font-size:22px; } h2 { font-size:17px; margin:28px 0 4px; border-top:1px solid var(--line); padding-top:14px; }
.q { color:var(--muted); margin:4px 0 10px; } .note { color:var(--open); }
table { border-collapse:collapse; width:100%; margin:6px 0 12px; } td,th { text-align:left; vertical-align:top;
  padding:4px 6px; border-bottom:1px solid var(--line); } th { color:var(--muted); font-weight:600; }
.confirmed { color:var(--ok); font-weight:600; } .wrong { color:var(--bad); font-weight:600; }
.open { color:var(--open); font-weight:600; } details { background:var(--card); border-radius:6px; padding:4px 8px; margin:4px 0; }
summary { cursor:pointer; } code, .m { font-family:ui-monospace,monospace; font-size:12px; word-break:break-word; }
.toc a { color:inherit; } .small { color:var(--muted); font-size:12px; }
"""


def esc(x):
    return html.escape(str(x if x is not None else ""))


def cls(verdict):
    v = verdict or ""
    if v.startswith("confirmed"):
        return "confirmed"
    if v.startswith("wrong"):
        return "wrong"
    return "open"


def anchor(name):
    return "i-" + "".join(c if c.isalnum() else "-" for c in name)


def page(root):
    root = layout.find_root(root)
    studies = []
    for f in layout.instance_folders(root):
        p = f / "study.json"
        if p.is_file():
            studies.append(json.loads(p.read_text()))
    studies.sort(key=lambda s: s["instance"])
    out = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>",
           f"<title>Study results</title><style>{CSS}</style></head><body>",
           f"<h1>Study results: {esc(root.name)}</h1>"]
    if studies:
        mb = studies[0]["made_by"]
        out.append(f"<p class='small'>Built by {esc(mb['tool'])} at safety {esc(mb['safety_rev'][:12])}"
                   f"{' (dirty)' if mb.get('dirty') else ''}.</p>")
    out.append("<div class='toc'><table><tr><th>Instance</th><th>Hypotheses</th><th>Notes</th></tr>")
    for s in studies:
        hs = " ".join(f"<span class='{cls(h['verdict'])}'>{esc(h['id'])}</span>" for h in s["hypotheses"])
        out.append(f"<tr><td><a href='#{anchor(s['instance'])}'>{esc(s['instance'])}</a></td><td>{hs}</td>"
                   f"<td>{len(s.get('notes', []))}</td></tr>")
    out.append("</table></div>")
    for s in studies:
        out.append(f"<h2 id='{anchor(s['instance'])}'>{esc(s['instance'])}</h2>")
        out.append(f"<div class='q'>{esc(s['question'])}</div>")
        out.append(f"<div class='small'>Board {esc(s.get('board') or '-')}; design {esc(s['design']['folder'])}; "
                   f"experiments: {esc(', '.join(e['name'] for e in s['experiments']) or '-')}</div>")
        if not s.get("state", {}).get("final", True):
            out.append(f"<div class='note'>Provisional: {esc('; '.join(s['state']['waits']))}</div>")
        for n in s.get("notes", []):
            out.append(f"<div class='note'>Note: {esc(n)}</div>")
        bad = [(a["run"], c) for a in s.get("acceptance", []) for c in a["checks"] if c["verdict"] != "confirmed"]
        if bad:
            out.append("<div class='small'>Acceptance checks that are not confirmed: " +
                       "; ".join(f"{esc(r)} {esc(c['id'])} {esc(c['verdict'])}" for r, c in bad) + "</div>")
        for r in s.get("rebuild_checks", []):
            out.append(f"<div class='small'>Rebuild check of {esc(r['run'])} on {esc(r['host'])}: {esc(r['summary'])}</div>")
        if s["hypotheses"]:
            out.append("<table><tr><th>Hypothesis</th><th>Claim</th><th>Verdict</th></tr>")
            for h in s["hypotheses"]:
                rows = "".join(
                    f"<tr><td>{esc(c['id'])}</td><td class='{cls(c['verdict'])}'>{esc(c['verdict'])}</td>"
                    f"<td class='m'>{esc(c.get('limit'))}</td><td class='m'>{esc(c.get('measured'))}</td></tr>"
                    for c in h["checks"])
                out.append(f"<tr><td>{esc(h['id'])}</td><td>{esc(h['statement'])}<details><summary>"
                           f"{esc(h['checks_confirmed'])} checks confirmed</summary><table><tr><th>Check</th>"
                           f"<th>Verdict</th><th>Limit</th><th>Measured</th></tr>{rows}</table></details></td>"
                           f"<td class='{cls(h['verdict'])}'>{esc(h['verdict'])}"
                           f"{' (provisional)' if h.get('provisional') else ''}</td></tr>")
            out.append("</table>")
        crs = [c for c in s["central_results"] if c.get("texts") or c.get("not_evaluated")]
        if crs:
            out.append("<table><tr><th>Central result</th><th>Result</th></tr>")
            for c in crs:
                body = "<br>".join(esc(t) for t in c.get("texts", [])) or f"<i>not evaluated: {esc(c['not_evaluated'])}</i>"
                if c.get("verdict"):
                    body += f" <span class='{cls(c['verdict'])}'>({esc(c['verdict'])}, by {esc(c.get('by'))})</span>"
                out.append(f"<tr><td>{esc(c['id'])}</td><td>{body}</td></tr>")
            out.append("</table>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"
