# code-place-q4

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`, and the clock drift:
the effect of the code address on the latency with hot code in RAM,
against a flash control.

## Method

- Tree `ws-safety`. Semaphore wake (`LATBENCH_WAKE_SEM`). 50000 samples
  per point. The same points on `ws-up` are in `code-place-q4-up`.
- The checks read the p50 of each histogram (`irq`, `isr2thr`) and the
  drift per wake (`clock_drift_cyc` / samples, default anchor only).
- Board time: about 35 s per point, with build and flash.
- The points are the cube `place` x `anchor` (point id
  `<place>-<anchor>`).

## Axes

- **place**: `f0` and `f4` are the flash control
  (`LATBENCH_CODE_FLASH_PAD`, pad 0 and 4 bytes). Their code layout is
  that of the reference points `p0` and `p4` of `code-layout`. `r0` ..
  `r28` have hot code in RAM (`LATBENCH_CODE_RAM`, pad 0, 4, .. 28
  bytes). The pad moves only the relocated code.
- **anchor**: `default` is time slicing, 20 ms, the default anchor.
  `noslice` (`TIMESLICING=n`) is the anchor without the slice reprogram
  of SysTick.
