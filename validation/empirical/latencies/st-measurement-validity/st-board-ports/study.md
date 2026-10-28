# board-ports

## Background

This study checks the port of the benchmark to a board. The question
of the study is in `study.yaml`: does the port build, flash, read the
console and give plausible data?

The study has one instance for each board. The folder of each instance
in the results is `board-ports@<port>`. An instance reads only the
experiment of its board.

## Experiments

Each experiment is a smoke test of one port. It uses the app
`wake_latency` with the board defaults, 10000 samples, on the trees
`ws-safety` and `ws-up`. `run.py` must build the image, flash the board
and read the console.

- `wake-port-smoke-nrf54l15dk`: the board `nrf54l15dk/nrf54l15/cpuapp`.
- `wake-port-smoke-nrf52840dk`: the board `nrf52840dk/nrf52840`.
- `wake-port-smoke-mimxrt1060_evk`: the board
  `mimxrt1060_evk@C/mimxrt1062/qspi`. The loopback wire is D2 - A3 (A3
  drives, D2 reads).

The study has no `hypotheses.yaml`. A person confirms the central result
`port-works`. The central result `irq-p50` gives the IRQ to ISR p50 of
each board, in cycles of the CPU clock of the board.

## References

- `ex-port-smoke-nrf54l15dk/experiment.md`,
  `ex-port-smoke-nrf52840dk/experiment.md`,
  `ex-port-smoke-mimxrt1060_evk/experiment.md`: the three smoke tests.
- `tests/benchmarks/boards.yaml`: the boards and their ports.
