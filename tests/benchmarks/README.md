# Latency benchmarks

Benchmarks that measure the distributions of interrupt and scheduling
latencies of Zephyr. All times are in counts of a hardware timer (core
cycles on the NUCLEO-G474RE). The full guide is the Sphinx document
`doc/benchmark-guide/`.

## Hardware

Only the NUCLEO-G474RE has data points. `boards.yaml` lists the other
boards; their ports build, but nobody ran them yet.

- NUCLEO-G474RE, connected through its ST-LINK (console at 115200
  baud). The probe and the console of each board are in the hardware
  map of the host, `hw-map.yml` (twister format, not checked in; see
  the guide, host tools).
- One wire from D2 (PA10) to A3 (PB0) on the Arduino header.
  - PA10 is also TIM2 channel 4. TIM2 makes the stimulus edge.
  - PB0 is on EXTI line 0, which has its own interrupt vector.

## Layout

| Path | Content |
|---|---|
| `trees.yaml` | Pinned Zephyr and module revs for each tree, and the SDK version |
| `boards.yaml` | For each board: port folder, modules, flash commands |
| `hw-map.yml` | Not checked in: the probe and the console of each board on this host (twister hardware map) |
| `common/` | Histogram, metadata, stimulus and load code, Kconfig fragments (`conf/`) |
| `common/boards/<board>/` | Board port: `port.cmake`, `port.c`, `include/latbench/port_impl.h`, overlays (see `common/include/latbench/port.h`) |
| `irq_latency/` | IRQ to ISR latency with a hardware time stamp of the edge |
| `wake_latency/` | Edge to ISR to woken thread, for each ISR-capable kernel object |
| `thread_latency/` | Thread to thread wake, for each kernel primitive |
| `loopback_check/` | Checks the wire |
| `unit/` | Unit tests for the histogram code and the scripts, without the board (see `unit/README.md`) |

The host scripts and the experiment files are in other folders. These
paths are relative to the root of the repo:

| Path | Content |
|---|---|
| `validation/empirical/latencies/<study>/<name>/experiment.yaml` | One folder for each experiment, in the folder of the study that owns it: app, trees, points, repetitions; `experiment.md` describes it |
| `scripts/benchmarks/trees.py` | Creates and checks the pinned worktrees |
| `scripts/benchmarks/run.py` | Runs an experiment and records its provenance |
| `scripts/benchmarks/hwmap.py` | Reads the hardware map and selects the entry of a board |
| `scripts/benchmarks/latbench.py` | Parses logs and prints percentiles |
| `scripts/benchmarks/plot.py` | Plots the exceedance probability and the histograms |
| `scripts/benchmarks/requirements.txt` | Python packages for the scripts |
| `scripts/benchmarks/tests/` | pytest modules for the scripts and the experiment files |

## Reproduce a data point

Each result folder has a `manifest.json`. It names the safety repo rev,
the experiment file, and the revs of all trees.

1. Check out the safety repo at the rev in `manifest.json` (`safety.rev`).
2. Create the pinned trees (once):

   ```sh
   scripts/benchmarks/trees.py setup
   ```

3. Run the experiment again:

   ```sh
   scripts/benchmarks/run.py validation/empirical/latencies/<study>/<name>/experiment.yaml --out <dir>
   ```

4. Compare the results:

   ```sh
   scripts/benchmarks/latbench.py summary <dir>/.../rep1.log <old>/.../rep1.log
   ```

`run.py` stops before it builds anything if one of these conditions is
not true:

- The safety repo is clean (no changes, no untracked files).
- Each tree is at its pinned rev and is clean.
- The Zephyr SDK has the pinned version.

A build uses only the modules of its tree (`ZEPHYR_MODULES`). It does not
use the modules or the Zephyr tree of a west workspace.

A run builds from a snapshot of the committed sources (`git archive` of
the safety rev into `<run>/src/`), not from the worktree. Work in the
worktree during a long run does not change what the run builds.

## Change a tree

Do not change a pinned rev in `trees.yaml`, because old results refer to
it. Add a new tree instead. A Zephyr patch for this study goes on a
branch (for example `tkaestner/latency-hooks`) in the Zephyr repo. Its
commit is the rev of the new tree.
