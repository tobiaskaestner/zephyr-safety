# code-layout

## What it measures

App `wake_latency`, metrics `irq` and `isr2thr`, and the clock drift:
the effect of the place of the code in flash on the latency.

## Method

- Tree `ws-safety`. Semaphore wake (`LATBENCH_WAKE_SEM`). 200000 samples
  per point.
- Code in flash with a pad (`LATBENCH_CODE_FLASH_PAD`).
  `LATBENCH_CODE_PAD_BYTES` sets the pad. `common/src/pad.c` moves all
  app and kernel code by this number of bytes. Nothing else changes.
- The run `20261025T060257Z` came before the choice
  `LATBENCH_CODE_PLACE`. It had no choice, but the code layout of each
  point is the same.
- The points are the cube `pad` x `anchor` (point id `<pad>-<anchor>`).

## Axes

- **pad**: `p0` .. `p28`, `LATBENCH_CODE_PAD_BYTES` = 0, 4, .. 28. The
  axis moves the code in steps of 4 bytes over 32 bytes.
- **anchor**: `default` is time slicing, the default anchor. `noslice`
  (`TIMESLICING=n`) is the anchor without the slice reprogram of
  SysTick.
