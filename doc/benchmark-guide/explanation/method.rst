Measurement method
==================

Why the stimulus comes from hardware
------------------------------------

If the measured software makes the stimulus itself, the CPU is never in
a critical section at that moment. Then the measurement shows only the
best case. The ``loopback_check`` app is an example: its main thread sets
the pin and then waits in a busy loop, so all its samples have the same
value.

For this reason, the apps of the suite use a hardware timer as the
stimulus. The timer sets the pin at a programmed time, which is
asynchronous to the software. The edge can come while the kernel holds a
lock, while the system timer ISR runs, or while the CPU sleeps. The time
stamp of the edge is the compare value of the timer, so it does not
depend on software.
