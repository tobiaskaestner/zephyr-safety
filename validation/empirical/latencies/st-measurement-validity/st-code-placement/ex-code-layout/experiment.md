# code-layout

## Question

How much does the place of the code in flash change the latency?

In `wake-threads-1m`, the same code with different array sizes gave two
groups: IRQ p50 86 or 82 cycles, clock drift 9.7 or 8.0 cycles per wake.
The difference between the trees in the ISR to thread p50 changed from 0
to 190 cycles from build to build. The code of these builds starts at
different addresses (`_isr_wrapper` at 0x...1870, 0x...1910, 0x...1904).

## Method

App `wake_latency`, semaphore wake (`LATBENCH_WAKE_SEM`), 200000 samples
per point, tree ws-safety, code in flash with a pad
(`LATBENCH_CODE_FLASH_PAD`).

`LATBENCH_CODE_PAD_BYTES` sets the pad. `common/src/pad.c` moves all app
and kernel code by this number of bytes. Nothing else changes.

The points are the cube of the axes `pad` and `anchor` (point id
`<pad>-<anchor>`).

| Point | Settings | Why |
|---|---|---|
| `p0-*` .. `p28-*` | `LATBENCH_CODE_PAD_BYTES` = 0, 4, .. 28 | Move the code in steps of 4 bytes over 32 bytes. |
| `*-default` | time slicing | The default anchor. |
| `*-noslice` | `TIMESLICING=n` | The anchor without the slice reprogram of SysTick. |

The choice `LATBENCH_CODE_PLACE` came after the run 20261025T060257Z.
Since then, the pad needs `LATBENCH_CODE_FLASH_PAD`. The run had no
choice, but the code layout of each point is the same.

## References

- `wake-threads-1m`: owned by `st-load-scaling/st-timeout-queue-cost`.
- The check of the placement choice: `../ex-code-place-q4/experiment.md`.
