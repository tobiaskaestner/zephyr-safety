# design-properties

## Background

The list `spec/tla/mc/expected.txt` has one line for each model run (67 lines). Each line gives
the expected result. A line that says `pass` also gives the number of distinct states and the
depth of the state graph. A different number means that the state space changed.

## Experiments

- `mc-expected`: TLC on all lines of the list, one worker, after the selftest of TLC. The kind
  makes one check for each line from the list. They are in the hypothesis `mc-expected-generated`
  of the built study. Do not write them again in `hypotheses.yaml`.

## References

- `ex-mc-expected/experiment.md`
- `spec/tla/tools/TOOLS.rst`: the rules for evidence (one worker, pinned jar, selftest).
