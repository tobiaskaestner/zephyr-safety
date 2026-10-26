# port-smoke-mimxrt1060_evk

## Question

Does the port of the benchmark to the board
`mimxrt1060_evk@C/mimxrt1062/qspi` work? `run.py` must build the image, flash the
board and read the console.

## Method

App `wake_latency` with the board defaults, 10000 samples, trees
ws-safety and ws-up.

The loopback wire is D2 - A3 (A3 drives, D2 reads).

| Point | Settings | Why |
|---|---|---|
| `default` | the board defaults | The first check of the port. |

## References

- The study `board-ports`: one instance for each board.
