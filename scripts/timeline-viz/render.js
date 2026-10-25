/*
 * Copyright (c) 2026 inovex GmbH
 * SPDX-License-Identifier: Apache-2.0
 *
 * Timing diagram renderer (latency-modes/template.html, tdl-svg.cjs and the
 * Sphinx extension timeline_viz). timeline(sc, env) returns one SVG string.
 *   sc   one scenario (see README.md; tdl.py writes it)
 *   env  {lanes, laneKeys, titles, width}: the context table of tdl.py,
 *        titles = true to add <title> tooltips for stand-alone SVG files,
 *        width = the smallest width of a schematic diagram (optional).
 * The SVG uses the colour tokens of the page (--c-dev, --panel, ...).
 */
(function (root) {
"use strict";

/* Lane kinds: colour token and legend name. */
const KINDS = {
  hw:   { color: "var(--c-hw)",   name: "Hardware (pin, EXTI, NVIC, exception entry, counters)" },
  dev:  { color: "var(--c-dev)",  name: "Device ISR (EXTI0)" },
  tick: { color: "var(--c-tick)", name: "SysTick ISR" },
  sw:   { color: "var(--c-sw)",   name: "PendSV (context switch)" },
  thr:  { color: "var(--c-thr)",  name: "Thread" },
  mask: { color: "var(--c-mask)", name: "Interrupts masked" },
};

/* Lane groups, top to bottom. */
const GROUPS = [
  { key: "core", title: "Core" },
  { key: "isr", title: "ISRs · high → low prio" },
  { key: "thr", title: "Threads · high → low prio" },
];

const prioRank = (p) => (p === "ZLI" ? -1 : p === "low" ? 1e3 : p);

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (n) => n.toLocaleString("en-US");

function niceStep(span, target) {
  const raw = span / target;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 5, 10]) if (raw <= m * p) return m * p;
  return 10 * p;
}

function patterns(id) {
  return `<defs>
    <pattern id="${id}-mask" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" fill="var(--panel)"/><line x1="0" y1="0" x2="0" y2="6" stroke="var(--c-mask)" stroke-width="2"/></pattern>
    <pattern id="${id}-mask-p" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
      <rect width="6" height="6" fill="var(--panel)"/><line x1="0" y1="0" x2="0" y2="6" stroke="var(--c-mask)" stroke-width="2"/></pattern>
    <pattern id="${id}-miss" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
      <rect width="5" height="5" fill="var(--panel)"/><line x1="0" y1="0" x2="0" y2="5" stroke="var(--c-dev)" stroke-width="2"/></pattern>
    <pattern id="${id}-unk" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="7" height="7" fill="var(--panel)"/><line x1="0" y1="0" x2="0" y2="7" stroke="var(--fg2)" stroke-width="1.2" stroke-dasharray="2 2"/></pattern>
  </defs>`;
}

/* Lanes of a scenario in display order: group, then priority, then the
   order of the context table. Each entry has the effective priority. */
function orderedLanes(sc, env) {
  const over = sc.prio || {};
  const rows = sc.lanes.map((k) => {
    const l = env.lanes[k];
    const prio = k in over ? over[k] : l.prio;
    return { key: k, lane: l, prio, gi: GROUPS.findIndex((g) => g.key === l.group) };
  });
  rows.sort((a, b) => a.gi - b.gi
    || (a.lane.group === "core" ? 0 : prioRank(a.prio) - prioRank(b.prio))
    || env.laneKeys.indexOf(a.key) - env.laneKeys.indexOf(b.key));
  return rows;
}

/* ---------- swimlane diagram ---------- */
function timeline(sc, env) {
  const LBL = 140, CHIP_X = 146, CHIP_W = 30, X0 = 186;
  const LANE_H = 26, LANE_GAP = 6, HEAD_H = 15, GROUP_GAP = 10, TOP = 34;
  let pieces = sc.pieces || [{ from: sc.from, to: sc.to, frac: 1, axis: sc.axis }];
  const GAP = pieces.length > 1 ? 40 : 0;
  // A schematic diagram has 1 pixel per unit: its width follows the axis,
  // so a box that is wide enough for its label in units is wide enough on
  // the screen. env.width makes it wider (more pixels per unit), so that
  // the diagrams of one document have the same scale. Other diagrams are
  // 980 pixels wide.
  const span = pieces.reduce((a, p) => a + p.to - p.from, 0);
  if (sc.schematic) pieces = pieces.map((p) => ({ ...p, frac: (p.to - p.from) / span }));
  const W = sc.schematic ? Math.max(X0 + span + GAP * (pieces.length - 1) + 14, env.width || 0) : 980, X1 = W - 14;
  const usable = X1 - X0 - GAP * (pieces.length - 1);
  let acc = X0;
  const px = pieces.map((p) => { const w = usable * p.frac; const r = { x: acc, w }; acc += w + GAP; return r; });
  const X = (p, t) => px[p].x + ((t - pieces[p].from) / (pieces[p].to - pieces[p].from)) * px[p].w;

  // vertical layout: group header, then its lanes
  const rows = orderedLanes(sc, env);
  const laneY = {}, heads = [];
  let y = TOP, lastGroup = null;
  for (const r of rows) {
    if (r.lane.group !== lastGroup) {
      if (lastGroup !== null) y += GROUP_GAP - LANE_GAP;
      heads.push({ y, group: GROUPS[r.gi], first: lastGroup === null });
      y += HEAD_H;
      lastGroup = r.lane.group;
    }
    laneY[r.key] = y;
    y += LANE_H + LANE_GAP;
  }
  const lanesBottom = y - LANE_GAP;
  const brTop = lanesBottom + 14;
  const BR_H = 22;
  const axisY = brTop + sc.brackets.length * BR_H + 8;
  const H = axisY + 40;
  const id = "sc-" + sc.id;
  const hit = (tip) => `<g class="hit" data-tip="${esc(tip)}">` + (env.titles ? `<title>${esc(tip)}</title>` : "");
  let o = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(sc.title)}" style="min-width:${W}px;max-width:100%;height:auto">${patterns(id)}`;

  // group headers and separators
  for (const h of heads) {
    if (!h.first) o += `<line x1="4" x2="${X1}" y1="${h.y - GROUP_GAP / 2 + 1}" y2="${h.y - GROUP_GAP / 2 + 1}" stroke="var(--rule)"/>`;
    o += `<text x="4" y="${h.y + 10}" font-size="9.5" letter-spacing="0.06em" fill="var(--fg2)">${esc(h.group.title.toUpperCase())}</text>`;
  }
  // lanes
  for (const r of rows) {
    const y0 = laneY[r.key], kind = KINDS[r.lane.kind];
    o += `<rect x="${X0}" y="${y0}" width="${X1 - X0}" height="${LANE_H}" fill="var(--faint)" opacity="0.6"/>`;
    o += `<rect x="4" y="${y0 + 7}" width="4" height="12" rx="1" fill="${kind.color}"/>`;
    o += `<text x="${LBL}" y="${y0 + LANE_H / 2 + 4}" text-anchor="end" font-size="12" fill="var(--fg)">${esc(r.lane.label)}</text>`;
  }
  // priority chips; lanes of one group with the same priority share one chip body
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if (r.lane.group === "core") continue;
    let j = i;
    while (j + 1 < rows.length && rows[j + 1].lane.group === r.lane.group && rows[j + 1].prio === r.prio) j++;
    const top = laneY[r.key] + 4, bot = laneY[rows[j].key] + LANE_H - 4;
    const same = j > i;
    const names = rows.slice(i, j + 1).map((q) => q.lane.label);
    const kindWord = r.lane.group === "isr" ? "IRQ priority" : "thread priority";
    const tip = same
      ? `Same ${kindWord} (${r.prio}): ${names.join(", ")}. These contexts cannot preempt each other. A pending one waits until the running one ends or blocks.`
      : `${r.lane.label}: ${kindWord} ${r.prio}.${sc.prio && r.key in sc.prio ? " Changed for this point." : ""}`;
    o += hit(tip);
    o += `<rect x="${CHIP_X}" y="${top}" width="${CHIP_W}" height="${bot - top}" rx="4" fill="${same ? "var(--fg)" : "var(--panel)"}" fill-opacity="${same ? 0.1 : 1}" stroke="var(--fg2)" stroke-width="${same ? 1.4 : 1}"/>`;
    for (let k = i; k <= j; k++) {
      const yk = laneY[rows[k].key];
      o += `<text x="${CHIP_X + CHIP_W / 2}" y="${yk + LANE_H / 2 + 4}" text-anchor="middle" font-size="10.5" font-weight="500" fill="var(--fg)">${esc(String(rows[k].prio))}</text>`;
      if (k < j) o += `<text x="${CHIP_X + CHIP_W / 2}" y="${yk + LANE_H + LANE_GAP / 2 + 3}" text-anchor="middle" font-size="10" fill="var(--fg2)">=</text>`;
    }
    o += `</g>`;
    i = j;
  }
  // piece breaks
  for (let i = 1; i < pieces.length; i++) {
    const bx = px[i].x - GAP / 2;
    o += `<path d="M${bx - 5} ${TOP - 6} l5 6 l-5 6 l5 6" fill="none" stroke="var(--fg2)" stroke-width="1.2"/>`;
    o += `<line x1="${bx}" y1="${TOP}" x2="${bx}" y2="${lanesBottom}" stroke="var(--fg2)" stroke-dasharray="2 4"/>`;
    o += `<text x="${bx}" y="${lanesBottom + 12}" text-anchor="middle" font-size="10.5" fill="var(--fg2)">${esc(sc.breakLabel || "")}</text>`;
  }
  // segments
  for (const s of sc.segs) {
    const p = s.p || 0, lane = env.lanes[s.lane], kind = KINDS[lane.kind];
    const x0 = X(p, s.t0), x1 = X(p, s.t1), w = Math.max(1.5, x1 - x0), y0 = laneY[s.lane];
    // a schematic diagram has no durations: no cycle count, solid outlines
    const cost = sc.schematic ? "" : ` ${fmt(s.t1 - s.t0)} cycles (${s.m ? "measured" : "estimate"}).`;
    const tip = `${lane.label}: ${s.label || s.s}.${cost}${s.tip ? " " + s.tip : ""}`;
    let fill = kind.color, op = 0.28, stroke = kind.color, dash = s.m || sc.schematic ? "" : "4 3", sw = 1.4;
    if (s.s === "wfi") { op = 0.10; dash = "1 3"; }
    if (s.s === "pending") { fill = "none"; op = 1; dash = "5 3"; sw = 1.6; }
    // a PRIMASK lock (from {primask}) has the other hatch direction
    if (s.s === "mask") { fill = `url(#${id}-mask${s.lock === "primask" ? "-p" : ""})`; op = 0.55; stroke = "var(--c-mask)"; dash = ""; sw = 1; }
    if (s.s === "miss") { fill = `url(#${id}-miss)`; op = 1; stroke = "var(--c-dev)"; }
    if (s.s === "unk") { fill = `url(#${id}-unk)`; op = 1; stroke = "var(--fg2)"; dash = "3 3"; }
    o += hit(tip);
    o += `<rect x="${x0}" y="${y0 + 1}" width="${w}" height="${LANE_H - 2}" rx="2" fill="${fill}" fill-opacity="${op}" stroke="${stroke}" stroke-width="${sw}" ${dash ? `stroke-dasharray="${dash}"` : ""}/>`;
    if (s.label && s.label.length * 6.6 + 10 < w) {
      const bg = s.s === "mask" || s.s === "miss" || s.s === "unk";
      const tx = x0 + w / 2;
      if (bg) {
        const tw = s.label.length * 6.6 + 8;
        o += `<rect x="${tx - tw / 2}" y="${y0 + 6}" width="${tw}" height="14" rx="2" fill="var(--panel)"/>`;
      }
      o += `<text x="${tx}" y="${y0 + LANE_H / 2 + 4}" text-anchor="middle" font-size="11" fill="var(--fg)">${esc(s.label)}</text>`;
    }
    o += `</g>`;
  }
  // event cursors
  const rowsUsed = [[], []];
  for (const e of sc.events) {
    const p = e.p || 0, x = X(p, e.t);
    const col = e.kind === "edge" ? "var(--c-dev)" : e.kind === "tick" ? "var(--c-tick)" : "var(--fg)";
    const dash = e.kind === "stamp2" ? "3 3" : "";
    o += `<line x1="${x}" y1="${TOP - 8}" x2="${x}" y2="${lanesBottom + 4}" stroke="${col}" stroke-width="${e.kind === "edge" ? 2 : 1.4}" ${dash ? `stroke-dasharray="${dash}"` : ""}/>`;
    // label box: centred, or moved to stay inside the plot; a second row
    // takes a label that would collide with one in the first row
    let anchor = "middle", lx = x;
    const tw = e.label.length * 7;
    if (lx - tw / 2 < X0 - 20) { anchor = "start"; lx = x + 4; }
    if (lx + tw / 2 > W) { anchor = "end"; lx = x - 4; }
    const b0 = anchor === "middle" ? lx - tw / 2 : anchor === "start" ? lx : lx - tw, b1 = b0 + tw;
    let row = rowsUsed.findIndex((r) => !r.some(([a, b]) => b0 < b + 8 && a < b1 + 8));
    if (row < 0) row = 0;
    rowsUsed[row].push([b0, b1]);
    o += `<text x="${lx}" y="${TOP - 13 - 12 * row}" text-anchor="${anchor}" font-size="11.5" font-weight="500" fill="${col}">${esc(e.label)}</text>`;
  }
  // brackets
  sc.brackets.forEach((b, i) => {
    const p = b.p || 0, x0 = X(p, b.t0), x1 = X(p, b.t1), yb = brTop + i * BR_H + 6;
    const dash = b.m ? "" : `stroke-dasharray="4 3"`;
    o += `<path d="M${x0} ${yb - 5} V${yb} H${x1} V${yb - 5}" fill="none" stroke="var(--fg)" stroke-width="1.3" ${dash}/>`;
    const tw = b.label.length * 6.6;
    let anchor = "middle", lx = (x0 + x1) / 2;
    if (x1 - x0 < tw + 8) { anchor = "start"; lx = x1 + 6; }
    if (anchor === "start" && lx + tw > W) { anchor = "end"; lx = x0 - 6; }
    if (anchor === "end" && lx - tw < 4) { anchor = "start"; lx = x1 + 6; }
    const bx = anchor === "middle" ? lx - tw / 2 : anchor === "start" ? lx : lx - tw;
    o += `<rect x="${bx - 4}" y="${yb - 6}" width="${tw + 8}" height="14" fill="var(--panel)"/>`;
    o += `<text x="${lx}" y="${yb + 4}" text-anchor="${anchor}" font-size="11" fill="var(--fg)">${esc(b.label)}</text>`;
  });
  // axes
  pieces.forEach((pc, i) => {
    const step = niceStep(pc.to - pc.from, Math.max(3, Math.round(8 * pc.frac)));
    o += `<line x1="${px[i].x}" y1="${axisY}" x2="${px[i].x + px[i].w}" y2="${axisY}" stroke="var(--rule)"/>`;
    if (!sc.schematic) for (let t = Math.ceil(pc.from / step) * step; t <= pc.to; t += step) {
      const x = X(i, t);
      o += `<line x1="${x}" y1="${axisY}" x2="${x}" y2="${axisY + 4}" stroke="var(--fg2)"/>`;
      o += `<text x="${x}" y="${axisY + 15}" text-anchor="middle" font-size="10.5" fill="var(--fg2)">${t}</text>`;
    }
    o += `<text x="${px[i].x + px[i].w / 2}" y="${axisY + 32}" text-anchor="middle" font-size="11" fill="var(--fg2)">${esc(pc.axis)}</text>`;
  });
  return o + `</svg>`;
}

const api = { KINDS, GROUPS, prioRank, esc, fmt, niceStep, patterns, orderedLanes, timeline };
if (typeof module !== "undefined" && module.exports) module.exports = api;
else root.TimingRender = api;
})(this);
