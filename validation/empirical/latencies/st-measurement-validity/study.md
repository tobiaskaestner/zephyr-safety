# measurement-validity

## Background

This study checks the measurement method. The question of the study is
in `study.yaml`: do the benchmark apps measure the latency of the
kernel, and not an effect of the measurement method, the code layout or
the host? The study has no experiments of its own. Its six sub-studies
give the answer.

The board is not fixed at this level. Each instance of a sub-study
names its board. The sub-study `board-ports` has one instance for each
board port (`board-ports@<port>` in the results).

## Experiments

- `stimulus-sampling`: does the random stimulus sample the latency
  distribution evenly over the kernel tick, and how many samples,
  stimulus seeds and load seeds does a value from the p50 to the max
  need? It gives the central result `tail-needs-seeds`.
- `clock-drift`: why does the kernel cycle counter lose cycles against
  the stimulus timer, and does the loss change the latency data? It
  gives the central result `drift-cause`.
- `code-placement`: how much does the address of the code change the
  latency, and which placement gives numbers that a comparison between
  trees and options can use? It gives the central result
  `placement-choice`.
- `mask-instrumentation`: do the interrupt mask hooks (M4) measure the
  mask time of each call site, and do they leave the image unchanged
  when they are off?
- `reproducibility`: does the same image give the same histograms on
  another host, does a rebuild give the same image, and does a new
  safety revision give the old data? It gives the central result
  `same-image-same-data`.
- `board-ports`: does the port of the benchmark to a board build,
  flash, read the console and give plausible data?

## References

- `st-stimulus-sampling/study.md`, `st-clock-drift/study.md`,
  `st-code-placement/study.md`, `st-mask-instrumentation/study.md`,
  `st-reproducibility/study.md`, `st-board-ports/study.md`: the
  sub-studies.
