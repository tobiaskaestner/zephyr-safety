# wake-clock-drift-fix

## What it measures

App `wake_latency`, `LAT META` keys `clock_drift_cyc` and
`clock_elapsed_cyc`: the clock drift with and without the option
`CORTEX_M_SYSTICK_RELOAD_GAP_COMP`, and with 256 load timers at three
values of the shortest SysTick reload.

## Method

- Tree `ws-up-driftfix`. Semaphore wake (`LATBENCH_WAKE_SEM`).
- 200000 samples per point.
- The cube has the axes `comp` and `anchor` (point id
  `<comp>-<anchor>`). Three explicit points (`t256-*`) change the load
  timers, the shortest SysTick reload and the histogram size.

## Axes

- **comp**: `nocomp` is the tree without the option, the control with
  the drift. `gapcomp` (`CORTEX_M_SYSTICK_RELOAD_GAP_COMP=y`) is the fix
  of the first cause.
- **anchor**: `default`, `noslice` and `switch`, as in `wake-clock-drift`:
  different numbers of reprograms.
- **timers**: `t0` for the cube points. `t256`
  (`LATBENCH_LOAD_TIMERS=256`) for the explicit points, all with
  `gapcomp`.
- **min_reload**: the shortest SysTick reload
  (`zephyr,min-timeout-cycles`). `min10us` is the default of the driver.
  `min50us` and `min200us` use the overlays `min_timeout_50us.overlay`
  and `min_timeout_200us.overlay` in
  `common/boards/nucleo_g474re/systick/`.
- **bins**: `hdefault` (the default bins of the app) for the cube
  points. `hcoarse` (2048 fine and 2048 coarse bins) for the explicit
  points.
