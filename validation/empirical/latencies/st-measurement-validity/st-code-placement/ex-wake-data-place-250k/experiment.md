# wake-data-place-250k

## What it measures

App `wake_latency` (semaphore, wrapped ISR, idle CPU), metrics `irq`,
`isr2thr` and `irq2thr`, with the hot code in the CCM SRAM and a data
pad of 0 to 32768 bytes (`LATBENCH_DATA_PAD`). The pad is an array in the
`.bss` of the app. The data of the kernel and the stacks come after it,
so the pad moves them. `LAT META msp` gives the top of the interrupt
stack.

## Method

- Tree `ws-up`, 250000 samples per point, random stimulus interval
  100..500 us.
- Hot code in the CCM SRAM (`LATBENCH_CODE_RAM`): the code does not move
  with the data pad.
- On the NUCLEO-G474RE, the RAM region of the build is SRAM1 (80 KB from
  `0x20000000`) and SRAM2 (16 KB from `0x20014000`).

## Axes

- **pad**: `d0` (no pad), `d8k`, `d24k` (the stacks stay in SRAM1),
  `d26k` (the same shift as the first witness build with 256 rows: the
  interrupt stack and the idle stack in SRAM2), `d32k`.
- **anchor**: `default` or `noslice` (`TIMESLICING=n`).
