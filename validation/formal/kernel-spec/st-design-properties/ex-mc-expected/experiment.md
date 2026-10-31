# mc-expected

TLC runs each model of `spec/tla/mc/expected.txt` once, with one worker and `-fp 0`. Before the
models, the job runs the selftest of TLC (`spec/tla/selftest/expected.txt`).

## Points

One point for each line of the list. The id of a point is `<module>:<config>`, for example
`MCKSem:default`. The kind reads the points from the list file. Do not copy them here.

## Values

A check reads these values of a point: `verdict` (the result of TLC, for example `pass` or
`fail:Inv_X`), `expected`, `states`, `depth`, `seconds` and `evidence`.

## Subject

The paths of `subject` in `experiment.yaml` are the paths that the result depends on. The
paths of `tools` are the tools.
