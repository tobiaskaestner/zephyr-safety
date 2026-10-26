# code-place-q4

## Question

Does hot code in RAM remove the effect of the code address on the
latency? This is question Q4 of the review of 2026-10-25 (items L2 and
L17 of `later.md`).

The decision to check: comparisons between trees and options use
`LATBENCH_CODE_RAM` (hot code in RAM, on nucleo_g474re in the CCM SRAM).
Absolute numbers use `LATBENCH_CODE_FLASH_PAD`, as a range over the pads.

## Method

App `wake_latency`, semaphore wake (`LATBENCH_WAKE_SEM`), 50000 samples
per point, tree ws-safety. The same points on ws-up are in
`code-place-q4-up`.

The points are the cube of the axes `place` and `anchor` (point id
`<place>-<anchor>`).

| Point | Settings | Why |
|---|---|---|
| `f0-*`, `f4-*` | `LATBENCH_CODE_FLASH_PAD`, pad 0 and 4 bytes | The flash control. The code layout is that of the reference points `p0` and `p4` of `code-layout`. |
| `r0-*` .. `r28-*` | `LATBENCH_CODE_RAM`, pad 0, 4, .. 28 bytes | The pad moves only the relocated code. |
| `*-default` | time slicing, 20 ms | The default anchor. |
| `*-noslice` | `TIMESLICING=n` | The anchor without the slice reprogram of SysTick. |

The checks read the p50 of each histogram (`irq`, `isr2thr`) and the
drift per wake (`clock_drift_cyc` / samples, default anchor only).

The p50 of these histograms and the drift per wake do not change with
the number of samples: in `clock-drift-layout`, 200000 against 1000000
samples changed the drift by 0.01 cycles per wake. Thus 50000 samples
are sufficient.

Board time: about 35 s per point, with build and flash.

## References

- The reference in flash: run `code-layout/20261025T060257Z` (safety
  `5a7d0a5`, 200000 samples, pads 0..28).
- The same points on ws-up: `../code-place-q4-up/experiment.md`.
- The commit of `LATBENCH_CODE_PLACE` (`48f1341`): the flash layout of
  `f0` and `f4` is that of `p0` and `p4`.
- `clock-drift-layout`: owned by `clock-drift`.
