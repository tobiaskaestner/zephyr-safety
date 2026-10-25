/*
 * Copyright (c) 2026 inovex GmbH
 * SPDX-License-Identifier: Apache-2.0
 *
 * Hover box of the timeline-viz diagrams: the text of the nearest
 * [data-tip] element under the pointer, as on the latency-modes page.
 * The <title> elements stay in the SVG for pages without this script;
 * the script removes them, so that the browser does not show a second
 * tooltip.
 */
(function () {
  "use strict";
  function init() {
    const boxes = document.querySelectorAll(".timeline-viz");
    if (!boxes.length) return;
    boxes.forEach((b) => b.querySelectorAll("[data-tip] > title").forEach((t) => t.remove()));
    const tip = document.createElement("div");
    tip.className = "timeline-viz-tip";
    tip.hidden = true;
    document.body.appendChild(tip);
    document.addEventListener("pointermove", (ev) => {
      const t = ev.target.closest && ev.target.closest(".timeline-viz [data-tip]");
      if (!t || !t.getAttribute("data-tip")) { tip.hidden = true; return; }
      tip.textContent = t.getAttribute("data-tip");
      tip.hidden = false;
      const r = tip.getBoundingClientRect();
      let x = ev.clientX + 14, y = ev.clientY + 14;
      if (x + r.width > window.innerWidth - 8) x = ev.clientX - r.width - 14;
      if (y + r.height > window.innerHeight - 8) y = ev.clientY - r.height - 14;
      tip.style.left = x + "px";
      tip.style.top = y + "px";
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
