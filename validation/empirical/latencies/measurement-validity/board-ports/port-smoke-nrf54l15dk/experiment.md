# port-smoke-nrf54l15dk

## Question

Does the port of the benchmark to the board
`nrf54l15dk/nrf54l15/cpuapp` work? `run.py` must build the image, flash the
board and read the console.

## Method

App `wake_latency` with the board defaults, 10000 samples, trees
ws-safety and ws-up.

| Point | Settings | Why |
|---|---|---|
| `default` | the board defaults | The smoke test of the port. |

## References

- The study `board-ports`: one instance for each board.
