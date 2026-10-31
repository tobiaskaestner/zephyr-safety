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
  the guide page "Make a hardware map").
- One wire from D2 (PA10) to A3 (PB0) on the Arduino header.
  - PA10 is also TIM2 channel 4. TIM2 makes the stimulus edge.
  - PB0 is on EXTI line 0, which has its own interrupt vector.

## Layout

| Path | Content |
|---|---|
| `boards.yaml` | For each board: port folder, modules, flash commands |
| `hw-map.yml` | Not checked in: the probe and the console of each board on this host (twister hardware map). In a lab space, the map is in the lab space |
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
| `validation/trees/<tree>.yml` | One west manifest for each tree: the pinned Zephyr and module revs, and the SDK version |
| `validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml` | One folder `ex-<name>` for each experiment, in the folder `st-<study>` of the study that owns it: app, trees, points, repetitions; `experiment.md` describes it |
| `scripts/probatrix/benchmarks/trees.py` | The pinned trees of `validation/trees/` as west workspaces (commands: `study.py trees setup / check / show`) |
| `scripts/probatrix/benchmarks/run.py` | Runs an experiment and records its provenance |
| `scripts/probatrix/benchmarks/hwmap.py` | Reads the hardware map and selects the entry of a board |
| `scripts/probatrix/benchmarks/latbench.py` | Parses logs and prints percentiles |
| `scripts/probatrix/benchmarks/plot.py` | Plots the exceedance probability and the histograms |
| `scripts/probatrix/benchmarks/study.py` | Design lint and templates, lab spaces, pinned trees, campaigns, study instances (run lists, seals), and the aggregates `run.json`, `experiment.json`, `study.json` (see the guide pages "The tool study.py", "Studies and their results" and "Lab spaces and campaigns") |
| `scripts/probatrix/benchmarks/data.py` | Loads a built instance for a notebook |
| `tests/benchmarks/<app>/scripts/extract.py` | The data of a run of the app as JSON (common part: `common/scripts/latextract.py`) |
| `tests/benchmarks/<app>/scripts/plot.py` | The standard plots of an experiment of the app (common part: `common/scripts/latplot.py`) |
| `scripts/probatrix/benchmarks/requirements.txt` | Python packages for the scripts |
| `scripts/probatrix/benchmarks/tests/` | pytest modules for the scripts and the experiment files |

## Reproduce a data point

Each result folder has a `manifest.json`. It names the safety repo rev,
the experiment file, and the revs of all trees.

1. Make a lab space (once). It gives the trees root, the SDK path, the
   hardware map and the Python environment of the host:

   ```sh
   mkdir <lab folder> && cd <lab folder>
   git clone <safety repo> safety
   python3 -m venv .venv && .venv/bin/pip install -r safety/scripts/probatrix/benchmarks/requirements.lock
   .venv/bin/python safety/scripts/probatrix/benchmarks/study.py lab init --repo safety
   ```

2. Check out the safety repo of the lab space at the rev in
   `manifest.json` (`safety.rev`).
3. In the lab folder, create the pinned trees that the run used (once):

   ```sh
   safety/scripts/probatrix/benchmarks/study.py trees setup <tree>
   ```

4. Run the experiment again:

   ```sh
   scripts/probatrix/benchmarks/run.py validation/empirical/latencies/st-<study>/ex-<name>/experiment.yaml --out <dir>
   ```

5. Compare the results:

   ```sh
   scripts/probatrix/benchmarks/latbench.py summary <dir>/.../rep1.log <old>/.../rep1.log
   ```

`run.py` stops before it builds anything if one of these conditions is
not true:

- The safety repo is clean (no changes, no untracked files).
- Each tree is at its pinned rev and is clean.
- The Zephyr SDK has the pinned version.

Each tree is a west workspace of its own (`study.py trees setup`), and a
build is `west build` in that workspace. The build uses only the modules
of its board from its tree (`ZEPHYR_MODULES`), never a module or a Zephyr
of another workspace.

A run builds the app from the safety repo. Before each point, `run.py`
makes sure that the repo is clean and at the commit of the start of the
run, and stops if not; it checks again after each build. The app gets
`LATBENCH_SRC_REV`, a content hash of the firmware files of
`tests/benchmarks` (no host scripts, Python or Markdown), and run.py gives
the Zephyr `BUILD_VERSION` (`git describe` of the tree) to CMake. In a lab space, the images go into the build
cache. A run of an older `run.py` has a copy of the repo in
`<run>/src/`. New runs have none.

## Change a tree

Do not change a pinned rev in `validation/trees/`, because old
results refer to it. Add a new tree instead. A Zephyr patch for this
study goes on a branch (for example `tkaestner/latency-hooks`) in the Zephyr repo. Its
commit is the rev of the new tree.
