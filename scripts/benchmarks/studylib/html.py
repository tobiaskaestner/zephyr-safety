# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The HTML pages of a results tree: index.html in each instance folder and in each experiment folder.

    <instance>/index.html        the links up to each parent; the question, the notes,
                                 the acceptance and rebuild checks, the hypotheses with
                                 each check, the central results; the experiments (with
                                 a link to their pages) and the direct sub-studies (with
                                 their verdicts in one line)
    <instance>/ex-<exp>/index.html
                                 the standard plots of the experiment (plots/, from the
                                 plot.py of its app) and its runs: role, reason, digest,
                                 campaign, acceptance; the failed runs

All links are relative, so the tree works in any place. No scripts, no
files from other places; the same tree gives the same bytes.
"""

import html
import json
from pathlib import Path

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
.crumbs { color:var(--muted); font-size:12px; } .crumbs a { color:inherit; }
.plot { background:#fcfcfb; border-radius:6px; padding:6px; margin:8px 0; max-width:100%; }
.plot img { width:100%; height:auto; display:block; }
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


def head(title):
    return ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width,initial-scale=1'>",
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"]


def verdict_line(s):
    """The verdicts of an instance in one line (as analysis show)."""
    hv = [h["verdict"].split(" ")[0] for h in s["hypotheses"]]
    parts = [f"<span class='{cls(h['verdict'])}'>{esc(h['id'])} {esc(h['verdict'].split(' ')[0])}</span>"
             for h in s["hypotheses"]]
    crs = s["central_results"]
    if crs:
        parts.append(f"central {sum(1 for c in crs if not c.get('not_evaluated'))} of {len(crs)}")
    if not s.get("state", {}).get("final", True):
        parts.append("<span class='note'>provisional</span>")
    return " &middot; ".join(parts) if (hv or crs) else "<span class='small'>no hypotheses</span>"


def study_body(s, out):
    """The content of the study.json of one instance."""
    out.append(f"<div class='q'>{esc(s['question'])}</div>")
    out.append(f"<div class='small'>Board {esc(s.get('board') or '-')}; design {esc(s['design']['folder'])}. "
               f"Built by {esc(s['made_by']['tool'])} at safety {esc(s['made_by']['safety_rev'][:12])}"
               f"{' (dirty)' if s['made_by'].get('dirty') else ''}.</div>")
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
        out.append("<h2>Hypotheses</h2><table><tr><th>Hypothesis</th><th>Claim</th><th>Verdict</th></tr>")
        for h in s["hypotheses"]:
            rows = "".join(
                f"<tr><td>{esc(c['id'])}</td><td class='{cls(c['verdict'])}'>{esc(c['verdict'])}</td>"
                f"<td class='m'>{esc(c.get('limit'))}</td><td class='m'>{esc(c.get('statement') or c.get('measured'))}"
                f"</td></tr>" for c in h["checks"])
            out.append(f"<tr><td>{esc(h['id'])}</td><td>{esc(h['statement'])}<details><summary>"
                       f"{esc(h['checks_confirmed'])} checks confirmed</summary><table><tr><th>Check</th>"
                       f"<th>Verdict</th><th>Limit</th><th>Measured</th></tr>{rows}</table></details></td>"
                       f"<td class='{cls(h['verdict'])}'>{esc(h['verdict'])}"
                       f"{' (provisional)' if h.get('provisional') else ''}</td></tr>")
        out.append("</table>")
    crs = [c for c in s["central_results"] if c.get("texts") or c.get("not_evaluated")]
    if crs:
        out.append("<h2>Central results</h2><table><tr><th>Central result</th><th>Result</th></tr>")
        for c in crs:
            body = "<br>".join(esc(t) for t in c.get("texts", [])) or f"<i>not evaluated: {esc(c['not_evaluated'])}</i>"
            if c.get("verdict"):
                body += f" <span class='{cls(c['verdict'])}'>({esc(c['verdict'])}, by {esc(c.get('by'))})</span>"
            out.append(f"<tr><td>{esc(c['id'])}</td><td>{body}</td></tr>")
        out.append("</table>")


def crumbs(folder, root, studies, up=0):
    """The links to the instance pages above folder ("../" * k), from the top down."""
    parts = []
    f, k = folder.parent, 1
    while f.resolve().is_relative_to(root.parent.resolve()) and (f / "instance.json").is_file():
        name = studies[f]["instance"].rsplit("/", 1)[-1] if f in studies else f.name
        parts.append(f"<a href='{'../' * (k + up)}index.html'>{esc(name)}</a>")
        f, k = f.parent, k + 1
    return "<div class='crumbs'>" + " / ".join(reversed(parts)) + "</div>" if parts else ""


def instance_page(folder, root, studies, design=None):
    s = studies[folder]
    out = head(f"{layout.display(s['instance'])}")
    out.append(crumbs(folder, root, studies))
    out.append(f"<h1>{esc(layout.display(s['instance']))}</h1>")
    study_body(s, out)
    if s["experiments"]:
        out.append("<h2>Experiments</h2><table><tr><th>Experiment</th><th>Runs</th></tr>")
        for e in s["experiments"]:
            names = design.names(e["name"]) if design is not None else [e["name"]]
            n = sum(1 for r in instance_runs(folder) if r["id"].split("/")[0] in names)
            out.append(f"<tr><td><a href='{layout.EXPERIMENT_PREFIX}{esc(e['name'])}/index.html'>{esc(e['name'])}</a>"
                       f"</td><td>{n}</td></tr>")
        out.append("</table>")
    nbi = folder / "notebooks" / "notebooks.json"
    if nbi.is_file():
        nbs = json.loads(nbi.read_text()).get("notebooks", {})
        out.append("<h2>Notebooks</h2><ul>")
        for name, n in sorted(nbs.items()):
            out.append(f"<li><a href='notebooks/{esc(n['html'])}'>{esc(name)}</a></li>" if n.get("html")
                       else f"<li>{esc(name)}: <span class='wrong'>failed</span> {esc(n.get('error'))}</li>")
        out.append("</ul>")
    subs = sorted(c for c in studies if c.parent == folder)
    if subs:
        out.append("<h2>Sub-studies</h2><table><tr><th>Sub-study</th><th>Verdicts</th></tr>")
        for c in subs:
            out.append(f"<tr><td><a href='{esc(c.name)}/index.html'>{esc(studies[c]['instance'].rsplit('/', 1)[-1])}</a>"
                       f"</td><td>{verdict_line(studies[c])}</td></tr>")
        out.append("</table>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"


def instance_runs(folder):
    try:
        return json.loads((folder / "instance.json").read_text()).get("runs", [])
    except (OSError, ValueError):
        return []


def experiment_page(folder, exp, root, studies, design_names=None):
    s = studies[folder]
    edir = folder / f"{layout.EXPERIMENT_PREFIX}{exp}"
    names = design_names or [exp]
    out = head(f"{exp} in {layout.display(s['instance'])}")
    out.append(crumbs(edir, root, studies) or "")
    out.append(f"<h1>{esc(exp)}</h1><div class='small'>in {esc(layout.display(s['instance']))}</div>")
    acc = {a["run"]: a["checks"] for a in s.get("acceptance", [])}
    runs = [r for r in instance_runs(folder) if r["id"].split("/")[0] in names]
    plots_file = edir / "plots" / "plots.json"
    if (edir / "plots" / "error.txt").is_file():
        out.append(f"<div class='note'>The plots failed: {esc((edir / 'plots' / 'error.txt').read_text().strip())}</div>")
    if plots_file.is_file():
        plots = json.loads(plots_file.read_text())
        out.append(f"<h2>Plots</h2><div class='small'>From the runs {esc(', '.join(plots['runs']))} "
                   f"(the plot.py of {esc(plots['app'])}).</div>")
        for kind in ("overview", "ccdf", "hist"):
            for p in [p for p in plots["plots"] if p["kind"] == kind]:
                title = p["metric"] + (f" {p['tree']}/{p['point']}" if "point" in p else "")
                out.append(f"<div class='plot'><img src='plots/{esc(p['file'])}' alt='{esc(kind)} of {esc(title)}'"
                           " loading='lazy'></div>")
    out.append("<h2>Runs</h2><table><tr><th>Run</th><th>Role</th><th>Digest</th><th>Campaign</th>"
               "<th>Acceptance</th></tr>")
    for r in runs:
        a = acc.get(r["id"], [])
        at = ", ".join(f"<span class='{cls(c['verdict'])}'>{esc(c['id'])} {esc(c['verdict'])}</span>" for c in a) or "-"
        role = esc(r["role"]) + (f": {esc(r.get('reason'))}" if r.get("reason") else "")
        out.append(f"<tr><td class='m'>{esc(r['id'])}</td><td>{role}</td><td class='m'>{esc(r['digest'][:19])}</td>"
                   f"<td class='m'>{esc(r.get('campaign') or '-')}</td><td>{at}</td></tr>")
    out.append("</table>")
    failed = []
    for name in names:
        for f in sorted((folder / f"{layout.EXPERIMENT_PREFIX}{name}").glob("*.failed.json")):
            try:
                d = json.loads(f.read_text())
            except (OSError, ValueError):
                continue
            failed.append(f"<tr><td class='m'>{esc(d.get('run'))}</td><td>{esc(d.get('step'))}</td>"
                          f"<td>{esc(d.get('error'))}</td></tr>")
    if failed:
        out.append("<h2>Failed runs (not in the run list)</h2><table><tr><th>Run</th><th>Step</th><th>Error</th></tr>"
                   + "".join(failed) + "</table>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"


def write_pages(root, below=None, design=None):
    """Write index.html of each instance and each of its experiments at and below `below`; return the files."""
    root = layout.find_root(root)
    studies = {}
    for f in layout.instance_folders(root):
        p = f / "study.json"
        if p.is_file():
            studies[f] = json.loads(p.read_text())
    below = Path(below or root).resolve()
    written = []
    for f, s in sorted(studies.items(), key=lambda x: str(x[0])):
        if not f.resolve().is_relative_to(below):
            continue
        target = f / "index.html"
        target.write_text(instance_page(f, root, studies, design))
        written.append(target)
        for e in s["experiments"]:
            names = design.names(e["name"]) if design is not None else [e["name"]]
            edir = f / f"{layout.EXPERIMENT_PREFIX}{e['name']}"
            edir.mkdir(exist_ok=True)
            (edir / "index.html").write_text(experiment_page(f, e["name"], root, studies, names))
            written.append(edir / "index.html")
    return written


def page(root):
    """The page of the top instance (tests and the old caller)."""
    root = layout.find_root(root)
    studies = {f: json.loads((f / "study.json").read_text()) for f in layout.instance_folders(root)
               if (f / "study.json").is_file()}
    return instance_page(root, root, studies)
