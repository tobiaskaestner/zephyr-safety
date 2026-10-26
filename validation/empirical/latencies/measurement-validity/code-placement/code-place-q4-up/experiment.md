# code-place-q4-up

## Question

Does hot code in RAM remove the difference between the trees that
changes from build to build? This is the second part of the check in
`code-place-q4`.

## Method

The points of `code-place-q4` that the tree comparison needs, on the
tree ws-up. App `wake_latency`, semaphore wake (`LATBENCH_WAKE_SEM`),
50000 samples per point.

| Point | Settings | Why |
|---|---|---|
| `f0-*`, `f4-*` | `LATBENCH_CODE_FLASH_PAD`, pad 0 and 4 bytes | The tree difference in flash, for comparison. |
| `r0-*`, `r4-*` | `LATBENCH_CODE_RAM`, pad 0 and 4 bytes | The tree difference in RAM at two pads. |
| `*-default`, `*-noslice` | as in `code-place-q4` | The two anchors. |

The tree difference is the value of ws-up minus the value of ws-safety
(`code-place-q4`) at the same point.

## References

- The design and the other points: `../code-place-q4/experiment.md`.
