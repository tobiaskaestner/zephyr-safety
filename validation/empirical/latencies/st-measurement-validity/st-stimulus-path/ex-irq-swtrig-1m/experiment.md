# irq-swtrig-1m

## What it measures

App `irq_latency` with `LATBENCH_SWTRIG`: in one image, the IRQ entry
latency from the edge (`irq`) and from a store to `NVIC->STIR` (`irq_sw`).
The same ISR takes both time stamps. The difference of the two histograms
is the cost of the hardware path of the stimulus (compare match, pin,
wire, input synchronizer, EXTI), free of the code placement effect.

## Method

- Tree `ws-up`, 1M samples per point, random stimulus interval 100..500
  us. Each edge sample is followed by a software sample. The trigger
  thread (priority 1) waits a random gap in the same range, reads TIM2
  (`t0`) and writes the response IRQ to STIR.
- Hot code in the CCM SRAM (`LATBENCH_CODE_RAM`).
- `LAT META sw_read_cyc` gives the bound of the offset of the software
  sample (method page of the guide, software trigger).

## Axes

- **path**: `wrapped` (through `_isr_wrapper`) or `direct`. The stock
  path cannot see a software pend, and a ZLI must not wake a thread.
- **background**: `idle` (the edge meets WFI) or `busy` (a busy thread at
  the lowest priority). The software trigger always meets the spinning
  trigger thread. Thus the clean hardware path is `irq` of `busy` minus
  `irq_sw`.
