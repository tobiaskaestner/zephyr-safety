# irq-scenarios-1m

## What it measures

App `irq_latency` with the choice `LATBENCH_IRQ_SCENARIO`: the four
scenarios of the upstream interrupt benchmark (Zephyr PR 117170) that the
study did not have, and the entry as their reference. The app page
(section Scenarios) defines each span and compares it with the upstream
span.

| Scenario | Histograms |
|---|---|
| `entry` | `irq` (edge, busy thread), `irq_sw` (STIR store) |
| `unlock` | `irq_unlock`: `irq_unlock()` to the ISR of a pending edge |
| `nested` | `irq_nested` (edge in a lower-priority ISR), `irq_nested_sw` (STIR in the lower-priority ISR) |
| `exit` | `irq_exit`: end of the ISR to the interrupted thread; `irq` |
| `burst` | `irq_b2b`: ISR entry to the next ISR entry in a burst of 16; `irq` |

## Method

- Tree `ws-up`, 1M samples per point, random stimulus interval 100..500
  us. In the scenarios the main thread drives each sample and spins
  between the samples.
- Hot code in the CCM SRAM (`LATBENCH_CODE_RAM`), so that the scenarios
  (different images) compare without the code placement effect.
- Witness table of the main histogram (64 rows, 100 cycles or more).
- The reference `entry` has a busy thread at the lowest priority
  (`LATBENCH_BG_BUSY`) and the software trigger (`LATBENCH_SWTRIG`):
  the CPU state of the scenarios is a running thread, not WFI.

## Axes

- **path**: `wrapped` (through `_isr_wrapper`) or `direct`.
- **scenario**: `entry`, `unlock` (hold 10 us after the edge), `nested`
  (spare IRQ 90 at priority 1), `exit`, `burst` (16 runs).
