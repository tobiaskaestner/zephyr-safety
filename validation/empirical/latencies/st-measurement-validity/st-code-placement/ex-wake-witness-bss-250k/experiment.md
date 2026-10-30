# wake-witness-bss-250k

## What it measures

The points of `wake-witness-250k` (sub-study `tail-witnesses`) at the
revision with the witness rows in `.bss` and without the second table of
the cost measurement: `wake_latency` (semaphore, idle CPU), with and
without a witness table of 256 rows, with and without time slicing. With
this revision the table moves the stacks by about 13 KB, and they stay
in SRAM1 (quick check: `msp` `0x20011140`).

## Method

- Tree `ws-up`, 250000 samples per point, random stimulus interval
  100..500 us.
- Hot code in the CCM SRAM (`LATBENCH_CODE_RAM`).

## Axes

- **witness**: `without` or `with` (`LATBENCH_TAIL`, 256 rows).
- **slicing**: `slice` (default) or `noslice` (`TIMESLICING=n`).
