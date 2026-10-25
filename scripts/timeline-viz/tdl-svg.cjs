#!/usr/bin/env node
/*
 * Copyright (c) 2026 inovex GmbH
 * SPDX-License-Identifier: Apache-2.0
 *
 * Render the cards of a tdl.py output as SVG.
 *
 * Usage: node tdl-svg.cjs <cards.json> <out-dir> [--dark]
 *        node tdl-svg.cjs --fragments < cards.json > svgs.json
 *
 * The first form writes one stand-alone SVG file per card. The files carry
 * the colour tokens of the page (light, and dark under prefers-color-scheme),
 * a panel background and <title> tooltips. --dark writes the dark tokens only.
 *
 * --fragments writes {"<card id>": "<svg ...>"} for SVG inline in an HTML
 * page (the Sphinx extension timeline_viz). The page sets the colour tokens.
 */
"use strict";
const fs = require("fs");
const path = require("path");
const R = require("./render.js");

const LIGHT = `--bg:#f4f5f6;--panel:#fcfcfb;--fg:#15171a;--fg2:#52565c;--rule:#dcdfe3;--faint:#eceef0;
  --c-dev:#eb6834;--c-tick:#6250d6;--c-sw:#1baf7a;--c-thr:#2a78d6;--c-hw:#8a8f96;--c-mask:#3a3d42;--c-zli:#6d7178;`;
const DARK = `--bg:#111213;--panel:#1a1a19;--fg:#f0efec;--fg2:#c3c2b7;--rule:#34373b;--faint:#232527;
  --c-dev:#d95926;--c-tick:#9085e9;--c-sw:#199e70;--c-thr:#3987e5;--c-hw:#8d9198;--c-mask:#c9ccd1;--c-zli:#a3a7ad;`;

function style(dark) {
  const tokens = dark ? `svg{${DARK}}` : `svg{${LIGHT}}@media (prefers-color-scheme: dark){svg{${DARK}}}`;
  return `<style>${tokens}
text{font-family:"IBM Plex Mono",ui-monospace,"SFMono-Regular",Menlo,monospace}</style>`;
}

function standalone(sc, env, dark) {
  const svg = R.timeline(sc, env);
  // keep the intrinsic size; drop the page's responsive style
  const open = svg.match(/^<svg [^>]*>/)[0];
  const fixed = open.replace(/ style="[^"]*"/, "").replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ');
  return fixed + style(dark) + `<rect width="100%" height="100%" fill="var(--panel)"/>` + svg.slice(open.length);
}

function fragments() {
  const data = JSON.parse(fs.readFileSync(0, "utf8"));
  const env = { lanes: data.lanes, laneKeys: data.laneKeys, titles: true };
  const out = {};
  for (const sc of data.cards) out[sc.id] = R.timeline(sc, env);
  process.stdout.write(JSON.stringify(out));
}

function main() {
  if (process.argv[2] === "--fragments") return fragments();
  const [, , input, outDir, ...flags] = process.argv;
  if (!input || !outDir) {
    console.error("usage: node tdl-svg.cjs <cards.json> <out-dir> [--dark]");
    process.exit(2);
  }
  const data = JSON.parse(fs.readFileSync(input, "utf8"));
  const env = { lanes: data.lanes, laneKeys: data.laneKeys, titles: true };
  fs.mkdirSync(outDir, { recursive: true });
  for (const sc of data.cards) {
    const file = path.join(outDir, `${sc.id}.svg`);
    fs.writeFileSync(file, standalone(sc, env, flags.includes("--dark")));
    console.log(file);
  }
}

main();
