# Latency benchmarks

Benchmarks that measure the distributions of interrupt and scheduling
latencies of Zephyr on a NUCLEO-G474RE. All times are in core cycles.

## Hardware

- NUCLEO-G474RE, connected through its ST-LINK (console on
  `/dev/ttyACM0`, 115200 baud).
- One wire from D2 (PA10) to A3 (PB0) on the Arduino header.
  - PA10 is also TIM2 channel 4. TIM2 makes the stimulus edge.
  - PB0 is on EXTI line 0, which has its own interrupt vector.

## Layout

| Path | Content |
|---|---|
| `trees.yaml` | Pinned Zephyr and module revs for each tree, and the SDK version |
| `experiments/*.yaml` | One file for each experiment: app, trees, points, repetitions |
| `scripts/trees.py` | Creates and checks the pinned worktrees |
| `scripts/run.py` | Runs an experiment and records its provenance |
| `scripts/latbench.py` | Parses logs and prints percentiles |
| `scripts/plot.py` | Plots the exceedance probability and the histograms |
| `scripts/requirements.txt` | Python packages for the scripts |
| `common/` | Histogram, metadata and TIM2 stimulus code, Kconfig fragments (`conf/`), clock overlays (`clocks/`) |
| `irq_latency/` | IRQ to ISR latency with a hardware time stamp of the edge |
| `wake_latency/` | Edge to ISR to woken thread, for each ISR-capable kernel object |
| `loopback_check/` | Checks the wire |

## Reproduce a data point

Each result folder has a `manifest.json`. It names the safety repo rev,
the experiment file, and the revs of all trees.

1. Check out the safety repo at the rev in `manifest.json` (`safety.rev`).
2. Create the pinned trees (once):

   ```sh
   tests/benchmarks/scripts/trees.py setup
   ```

3. Run the experiment again:

   ```sh
   tests/benchmarks/scripts/run.py tests/benchmarks/experiments/<name>.yaml --out <dir>
   ```

4. Compare the results:

   ```sh
   tests/benchmarks/scripts/latbench.py summary <dir>/.../rep1.log <old>/.../rep1.log
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
