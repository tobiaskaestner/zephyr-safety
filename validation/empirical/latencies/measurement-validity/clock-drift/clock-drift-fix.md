# clock-drift-fix

## Question

Is the reprogram of SysTick the cause of the clock drift of
`clock-drift`? Does a second cause make the drift larger with many load
timers?

## Method

App `wake_latency`, semaphore wake (`LATBENCH_WAKE_SEM`), 200000 samples
per point, tree ws-safety-driftfix.

The tree ws-safety-driftfix adds the option
`CORTEX_M_SYSTICK_RELOAD_GAP_COMP` to the SysTick driver. With this
option, the driver measures the uncounted cycles of each reprogram with
the DWT cycle counter. It then adds them to the software count.

The cube has the axes `comp` and `anchor` (point id `<comp>-<anchor>`).
Three explicit points (`t256-*`) change the load timers, the shortest
SysTick reload and the histogram size.

| Point | Settings | Why |
|---|---|---|
| `nocomp-*` | the tree without the option | The control: the same tree with the drift. |
| `gapcomp-*` | `CORTEX_M_SYSTICK_RELOAD_GAP_COMP=y` | The fix of the first cause. |
| `*-default`, `*-noslice`, `*-switch` | as in `clock-drift` | The anchors of `clock-drift`, with different numbers of reprograms. |
| `t256-min10us-gapcomp` | gapcomp, `LATBENCH_LOAD_TIMERS=256`, 2048 fine and 2048 coarse bins | The second cause at the shortest reload of the driver (10 us). |
| `t256-min50us-gapcomp` | as above, overlay `min_timeout_50us.overlay` | The shortest reload is 50 us. |
| `t256-min200us-gapcomp` | as above, overlay `min_timeout_200us.overlay` | The shortest reload is 200 us. |

The second cause: the driver programs a reload of 10 us or more
(`min_delay`), and it sees one counter wrap or less. With 256 periodic
timers, the kernel masks the SysTick IRQ for longer than that, because
each timeout insert walks the list under the lock. Thus the driver can
lose whole reloads. An unpinned check gave a drift of 4668 ppm.

The overlays set `zephyr,min-timeout-cycles`. They are in
`common/boards/nucleo_g474re/systick/`.

## References

- The first cause and the anchors: `clock-drift.md`.
