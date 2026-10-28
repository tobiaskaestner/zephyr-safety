0001. The stimulus comes from hardware
======================================

Status
------

Accepted, 2026-10-24.

Problem
-------

A latency measurement needs the time of the event (the edge) and the time
of the reaction. If the measured software makes the event itself (a
software interrupt, a GPIO write), the CPU is never in a state that it
does not expect: it is not in WFI, not in a locked section, not in a long
ISR. The measurement then misses the latencies that matter.

Decision
--------

A hardware timer of the board makes the stimulus edge on a pin, at a time
that the software does not know in advance (random or fixed). A wire takes
the edge to an interrupt pin. A timer capture gives the time of the edge
in hardware. The software only reads the time of its reaction.

Results
-------

- Each board needs a board port with a timer output, a capture and a wire
  (see :doc:`../../reference/boards`).
- The wire check (``lab hwcheck``) is part of each campaign.
- The method can see the effect of WFI, of locked sections and of the
  tick (see :doc:`../method`).
