# zephyr-versions

## Background

The question of the study is in `study.yaml`: how do the three
latencies and their growth with the load change from one Zephyr version
to the next?

The other studies measure one Zephyr version, the tree `ws-up`. This
study compares versions. Each version is a tree in `validation/trees/`.
Later the experiments of this study get one tree for each version of
the comparison, for example v3.7, v4.0, v4.4 and v4.5. Now each
experiment runs on `ws-up` only, so the study has no comparison yet.

The experiments came from other studies. Each of them ran on two trees,
`ws-safety` and `ws-up`. The studies that used them now read them with
imports (`mode: reuse`). Thus their hypotheses and central results get
the data of `ws-up`.

A comparison of versions must not depend on the code address. In flash,
the difference between two trees changed from 0 to 190 cycles from
build to build (`wake-threads-1m`). The study `code-placement` found
that hot code in RAM removes this effect. H1 of this study checks that
the difference between two versions stays the same with code in RAM.

## Experiments

The study owns these experiments. The study that used each experiment
before is in parentheses.

- `irq-baseline-1m` (`default-latencies/irq-entry`): the IRQ entry of
  the four interrupt paths, 1M samples.
- `wake-anchors-1m` (`default-latencies/isr-to-thread`): the anchors of
  the ISR to thread wake.
- `thread2thread-1m` and `thread2thread-switch`
  (`default-latencies/thread-to-thread`): the thread to thread wake,
  and the wake with the new context switch.
- `systick-prio-1m` (`load-scaling/systick-priority`): the SysTick
  priority under timer load.
- `timeout-backends-1m`, `wake-threads-1m` and `wake-timers-1m`
  (`load-scaling/timeout-queue-cost`): the growth with the load and the
  timeout queue backends.
- `clock-drift` and `clock-drift-layout` (`measurement-validity/clock-drift`):
  the drift of the kernel cycle counter.
- `code-place-q4-up` (`measurement-validity/code-placement`): the points
  of `code-place-q4` that a comparison of two trees needs.

The study imports `code-place-q4` from `measurement-validity/code-placement`
for H1.

## Open points

- The central result `tree-diff` and the checks of H1 compare
  `code-place-q4-up` with `code-place-q4`. They compare two versions only
  when the two experiments run on different trees.
- The statistic `tree_diff` has the tree names `ws-up` and `ws-safety`
  in the tools. A comparison of versions needs a form with the names of
  the trees.
- When an experiment of this study runs on more than one tree, the
  imports give all trees to the other studies. Their checks then must
  select one tree.

## References

- `hypotheses.yaml`: H1, the version difference in RAM.
- `st-measurement-validity/st-code-placement/study.md`: the effect of
  the code address.
- `validation/trees/`: the trees.
