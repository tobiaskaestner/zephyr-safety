# reproducibility

## Background

TLC with one worker and `-fp 0` is deterministic: the same models give the same verdicts and the
same number of distinct states and depth. This study runs the list of `design-properties` a
second time and compares the two runs.

## Experiments

The study has no experiment of its own. It runs `mc-expected` again (the import with mode
`rerun`). The kind makes the checks of each line for the second run too.

## References

- `st-design-properties/ex-mc-expected/experiment.md`
