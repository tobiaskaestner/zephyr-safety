# kernel-spec

## Background

This study asks if the TLA+ spec of the kernel (`spec/tla`) is consistent, and if the code
conforms to it. The question is in `study.yaml`. The study has no experiments of its own. Its
sub-studies give the answer.

The kind of the study is `tlaplus`. A run is a run of TLC on the models of a list file. The
result of a run counts only for a subject: the git trees of the paths that the experiment names
in `subject`.

## Sub-studies

- `design-properties`: does each model of the list `spec/tla/mc/expected.txt` give its expected
  result, with the recorded number of states and depth?
- `reproducibility`: does a second run of the same list give the same result?

## References

- `st-design-properties/study.md`, `st-reproducibility/study.md`: the sub-studies.
- `spec/tla/tools/TOOLS.rst`: the tools and the rules for evidence.
