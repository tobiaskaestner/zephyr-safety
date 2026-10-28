# wake-m4-validate

## What it measures

App `wake_latency`, metrics `m4.mask`, `m4.isr` and the M4 calibration
(`m4_floor_cyc`, `m4_pair_cost_cyc`): the interrupt mask time of each
call site, against a calibration, a probe of a known length and the IRQ
tail.

## Method

- Tree `ws-up-irqoff` with `CONFIG_ARM_IRQ_MASK_HOOKS` and
  `CONFIG_ARM_IRQ_MASK_HOOKS_ISR`.
- Semaphore given from the wrapped ISR, idle background, time slicing
  on.
- 200000 samples per point. All values are in cycles at 170 MHz.
- The latency histograms are smaller than in the 1M runs: 1024 fine bins
  and 1024 coarse bins of 64 cycles, 0..66559 cycles. The site table
  needs the RAM (64 sites x 488 bytes).
- The latency histograms are not data (`LAT META m4=1`). The analysis
  uses the M4 tables (`scripts/benchmarks/m4.py`) only.
- No cube: seven explicit points that change several factors. The axis
  names are the names of `wake-timers-1m`, `wake-systick-prio-1m` and
  `wake-timeout-backends-1m`.

## Axes

- **timers**: `t0` (no load), `t64` or `t256` periodic load timers
  (`LATBENCH_LOAD_TIMERS`).
- **prio**: `same` is SysTick at the driver priority. `lower`
  (`LATBENCH_SYSTICK_PRIO=1`) is SysTick one level lower.
- **backend**: `dlist` (the default) or `wheel` (`TIMEOUT_BACKEND_WHEEL`,
  point `t256-wheel`).
- **probe**: `none`, or `5000cyc` (point `probe-t0`): a probe thread
  masks for exactly 5000 DWT cycles every 10 ms
  (`LATBENCH_IRQMASK_PROBE_CYC`, `LATBENCH_IRQMASK_PROBE_MS`).
