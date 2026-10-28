.. _benchguide-hw-map:

Hardware map (``hw-map.yml``)
=============================

The hardware map tells ``run.py`` which probe and which serial port a
board has on this host. It is a twister hardware map (see the Zephyr
documentation, "Executing tests on multiple devices"). It is not in the
repository: ``tests/benchmarks/.gitignore`` lists ``hw-map.yml``. In a
lab space, the map is ``[hardware] map`` of ``.lab/config`` (default
``<lab folder>/hw-map.yml``). Outside a lab space, the default is
``tests/benchmarks/hw-map.yml``.

:doc:`../../howto/make-a-hardware-map` tells how to make the map.

``run.py`` reads the map only when it flashes (not with ``--dry-run``,
``--build-only`` or ``--rebuild``). It checks the map against the twister
schema of the first tree of the experiment
(``scripts/schemas/twister/hwmap-schema.yaml``). Then it selects the one
entry with ``connected: true``, the board target in ``platform`` and the
fixture ``latbench_loopback``. ``probe_id`` replaces ``id`` as the probe
ID, as in twister. ``baud`` or ``serial_baud`` sets the baud rate
(default 115200). The manifest records the entry in ``hardware``.

The map has no data that changes a measurement, so it is not part of the
provenance of a data point. The manifest records it for the
investigation of a failed run.
