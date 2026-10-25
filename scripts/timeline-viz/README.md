# timeline-viz: timing diagrams from text

timeline-viz makes swimlane timing diagrams from text files. The text
format is TDL (timing diagram language). One TDL file describes one
diagram: which context runs, for how long, and what is measured. It does
not state colours, pixel sizes, lane order or label positions. The
renderer calculates these.

There are three users of the same renderer, so a diagram looks the same
in all three:

- the Sphinx directive `timeline-viz::` (`doc/_extensions/timeline_viz`),
- the latency-modes page of the latency study (`latency-modes/`),
- stand-alone SVG files (`tdl-svg.cjs`).

## Files

| File | Content |
|---|---|
| `tdl.py` | Compiler: TDL to JSON (`tdl.py compile <file.tdl>...`) |
| `render.js` | Renderer: one compiled diagram to SVG. Runs in the browser and in Node |
| `tdl-svg.cjs` | Command line: JSON to stand-alone SVG files, or to inline SVG (`--fragments`) |
| `contexts/*.tdc` | Context files. `g474.tdc` has the contexts of the NUCLEO-G474RE benchmark apps |
| `latency-modes/` | The latency-modes page: `build.py`, `template.html` and one card per file in `cards/` |
| `tests/` | pytest tests of the compiler, the renderer and the Sphinx extension |

The tools need Python 3 and Node (18 or later). The Sphinx extension also
needs Node on `PATH`. There are no other dependencies.

## Usage

### In the documentation

The document `conf.py` loads the extension `timeline_viz` (see
`doc/_extensions/README.rst`). Then:

```rst
.. timeline-viz:: diagrams/isr-to-thread.tdl
   :name: fig-isr-to-thread

   The caption. Without content, the caption is the diagram title.
```

- The path is relative to the document. A path that starts with `/` is
  relative to the source folder. zdocs copies the document folder into
  the build folder, so put the TDL files in the document folder.
- `:name:` gives a label for `:ref:`.
- `:width:` is the smallest width in pixels (default 760, config value
  `timeline_viz_min_width`). In a narrower column, the diagram scrolls
  in its box.
- An `include` looks for the context file next to the TDL file, then in
  each folder of the config value `timeline_viz_include_path` (relative
  to the source folder), then in `contexts/` of this tool.
- A TDL error is a build error with the file and the line.
- The diagram is in the HTML output only. Other builders show the
  caption and a note.

### Stand-alone SVG files

```console
scripts/timeline-viz/tdl.py compile diagram.tdl -o /tmp/cards.json
node scripts/timeline-viz/tdl-svg.cjs /tmp/cards.json /tmp/svg/
```

The SVG files have light and dark colours (`--dark`: dark only) and
`<title>` tooltips.

### The latency-modes page

```console
scripts/timeline-viz/latency-modes/build.py --results <results folder> -o latency-modes.html
```

`<results folder>` holds the result folders of `run.py`. `build.py`
reads the histograms of the runs that `HISTS` and `CCDFS` name, and puts
them, the compiled cards and `render.js` into `template.html`. The card
order is the list `SCENARIOS` in the template.

### Tests

```console
pytest scripts/timeline-viz/tests
```

## Status (2026-10-25)

- All 18 cards of the latency-modes page come from `latency-modes/cards/*.tdl`.
  The page template has no scenario data of its own.
- 16 cards were hand-written JavaScript before. Five of them were written
  again by hand in TDL (`a`, `b`, `e-slow`, `g2`, `h-slow`). A one-off
  script converted the other eleven. A field-by-field comparison showed
  that all 16 give the same scenario as the hand-written version (same
  steps, time points, spans and texts). The page then gave the same SVG
  elements for each card.
- `hsw-fast` and `hsw-slow` are the first cards that exist only in TDL.
  They use lock attributes instead of explicit mask times.
- The converted cards use explicit times for their time points
  (`@t0_1 edge "edge" at 0`). Rewrite them with named time points
  when you change them.
- The lane kinds (`device`, `tick`, `switch`, `thread`) and their
  legend names in `render.js` are those of the latency study.

## The abstractions

1. **Contexts, not lanes.** A context file declares each run context
   once: the hardware, the interrupt mask, each ISR with its IRQ
   priority, each thread with its thread priority. The renderer makes
   the lane groups (core, ISRs, threads), sorts the lanes by priority,
   and joins the priority chips of lanes with the same priority.
2. **One CPU, one sequence.** On one core only one context runs at a
   time. So most of a diagram is a list of steps with durations. The
   compiler adds the start times. Only parallel things (a peripheral
   counter, a pending IRQ, a blocked thread) need explicit times.
3. **States that come from the sequence.** "Pending until it runs" and
   "blocked until it runs" have an open end (`edge..`). The compiler
   ends them at the next step of that context.
4. **Locks as attributes.** A step with `{basepri}` or `{primask}` runs
   with that mask. The compiler merges such steps into the mask lane.
5. **Measured or not.** A duration with `!` is measured (solid
   outline). A duration with `?` is a cost whose place in the path is
   not known (hatched). All other durations are estimates (dashed).
6. **Named time points.** `@name` sets a time point. Cursors, spans and
   later times refer to it (`stamp1+1366`).

## Syntax

One statement per line. `#` starts a comment. A line that starts with
a space continues the previous statement. Text in double quotes is a
label. Text after ` : ` is the tooltip of the statement.

Time: a number of cycles (`-100`, `1757`), a time point (`edge`), or a
time point with an offset (`stamp1+1366`).

### Context file (`.tdc`)

```
core   hw     "Hardware"
core   mask   "PRIMASK, BASEPRI"
isr    dev    0    "EXTI0 ISR"
isr    tick   0    "SysTick ISR"       as tick
isr    pendsv low  "PendSV"            as switch
thread waker  0    "Woken thread"
```

- `isr <id> <prio> "<label>"`: an ISR. The priority is a number
  (IRQ_CONNECT() number, 0 is the highest), `ZLI` or `low`.
- `thread <id> <prio> "<label>"`: a thread.
- `as <kind>`: the colour family (`device`, `tick`, `switch`). The
  default is `device` for an ISR and `thread` for a thread.
- The order in the file is the order of lanes with the same priority.

### Diagram file (`.tdl`)

Header:

```
include g474.tdc
diagram e-slow "ISR → thread, slow mode (80 %): the slice reset reprograms SysTick"
axis "cycles after the edge" -100..1850
prio tick 1                     # optional: change a priority for this diagram
```

`include` finds the context file next to the diagram, then in each
folder of `tdl.py -I` (or of `timeline_viz_include_path` in Sphinx),
then in `contexts/`.

A broken axis has more than one piece. The statements after a `piece`
line belong to that piece:

```
piece "cycles after the SysTick IRQ" -100..1000
break "0 to 98.7 ms later"
...
piece "cycles after the edge" -30..80
```

Steps:

```
<context> [style] <duration>[!|?] ["label"] [{basepri|primask}] [: tooltip]
<context> [style] <from>..<to>[!|?] ["label"] ...
<context> [style] <from>.. ["label"] ...
```

| Form | Meaning |
|---|---|
| `dev 250 "k_sem_give()"` | Starts at the cursor, takes 250 cycles. The cursor moves to its end. |
| `hw 0..4 "pin"` | Fixed times. The cursor does not move. |
| `dev pending edge.. "pending"` | From `edge` to the next step of `dev`. |
| `at 0` | Sets the cursor. |

Styles: `run` (the default), `sleep` (WFI), `pending` (waits: pending
IRQ, blocked or preempted thread), `miss` (flash cache miss).

Time points, cursors and spans:

```
@edge                              # time point at the cursor; drawn as the edge cursor
@stamp1 "stamp 1"                  # drawn as a time stamp
@tick0 tick "SysTick IRQ" at -400  # kinds: edge, tick, stamp, ref (dashed), anchor (not drawn)
span stamp1..stamp2 "1676, measured" !
```

Card text (used by the page, ignored by the SVG tool):

```
letter "E slow"
new
num value "1676 cycles"
what "The same path as the fast mode, with one more step."
evidence "Two exact modes, 310 cycles apart."
src "wake-isr-1m/20261024T170705Z"
```
