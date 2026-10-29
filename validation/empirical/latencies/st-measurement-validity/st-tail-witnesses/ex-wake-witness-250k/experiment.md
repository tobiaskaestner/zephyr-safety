# wake-witness-250k

## What it measures

App `wake_latency` (semaphore, wrapped ISR, idle CPU), metrics `isr2thr`
and `irq2thr`, with and without the witness table `tail.irq2thr`
(`LATBENCH_TAIL`, 256 rows). The pairs show if the witness code changes
the wake path. The labels of the rows show if SysTick was reprogrammed
or interrupted during each sample, with and without time slicing.

## Method

- Tree `ws-up`, 250000 samples per point, random stimulus interval
  100..500 us.
- Hot code in the CCM SRAM (`LATBENCH_CODE_RAM`).
- The witness add runs in the woken thread after its time stamps. With
  256 rows, an add that stores a row scans the table (some thousand
  cycles), before the thread arms the next edge.

## Axes

- **witness**: `without` or `with` (256 rows, all samples are candidates).
- **slicing**: `slice` (default) or `noslice` (`TIMESLICING=n`). Without
  slicing, the wake path does not reprogram SysTick.
