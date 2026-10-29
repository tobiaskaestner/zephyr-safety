# irq-witness-1m

## What it measures

App `irq_latency`, direct path, idle CPU, metric `irq`, with and without
the witness tables (`LATBENCH_TAIL`). With the witnesses, the table
`tail.irq` keeps the 64 largest samples of 100 cycles or more, with the
counters of their windows and the interrupted PC. The pairs with and
without witnesses show if the witness code changes the latency. The
tables give the cause of each tail sample, without load and with 16
load timers.

## Method

- Tree `ws-up`, 1M samples per point, random stimulus interval 100..500
  us, direct path, idle CPU.
- Hot code in the CCM SRAM (`LATBENCH_CODE_RAM`).
- `LAT META tail_cost_*_cyc` gives the cost of the witness calls.

## Axes

- **witness**: `without` or `with` (`LATBENCH_TAIL`, 64 rows, smallest sample
  100 cycles).
- **load**: `none` or `t16` (`LATBENCH_LOAD_TIMERS=16`: 16 periodic
  timers, 10..100 ms). The load timers expire in the SysTick ISR.
