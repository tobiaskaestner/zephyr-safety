.. _benchguide-app-loopback-check:

``loopback_check``
==================

The :term:`app` ``loopback_check`` is in ``tests/benchmarks/loopback_check/``.
This page is its documentation, beside its code. The app is the
:term:`wire check` of the lab. :doc:`/explanation/apps` lists all apps.

What it measures
----------------

The app does a test of the wire without the stimulus timer and without a
board port. It drives the stimulus pin (``stim-gpios``) as a GPIO output
and reads the response pin (``resp-gpios``). Each board has an overlay in
``loopback_check/boards/`` with the same wire as its port. On the
MIMXRT1060-EVKC, A3 drives and D2 reads. The ``testcase.yaml`` permits
only ``nucleo_g474re``.

#. Static check: it drives the stimulus pin low and high and reads the
   response pin.
#. Interrupt check: 1000 times, it sets the stimulus pin high and measures
   the time to the GPIO callback of the response pin with
   ``timing_counter_get()``.

Options, variants and output
----------------------------

The app prints ``RESULT: OK`` or ``RESULT: FAIL``. It does not use the
``LAT`` line format. The ``use_switch`` scenario of its ``testcase.yaml``
builds it with ``CONFIG_USE_SWITCH=y``.
