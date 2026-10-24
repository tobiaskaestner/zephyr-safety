# Unit tests for the histogram code

These tests find errors in the histogram code of the benchmarks. They do
not use the board.

| Path | Content |
|---|---|
| `hist/` | Zephyr ztest app for `common/include/latbench/hist.h` and `common/src/hist.c` |
| `../scripts/tests/test_latbench.py` | pytest module for `scripts/latbench.py` and `scripts/plot.py` |
| `../scripts/tests/fixtures/hist_*.log` | Console output of the ztest app, one log for each scenario |

## Scenarios of the ztest app

| Scenario | Fine bins | Coarse bins | Phase bins |
|---|---|---|---|
| `latbench.unit.hist.fine` | 4096 | 0 | 64 |
| `latbench.unit.hist.coarse` | 16 | 4 of 4 cycles | 8 |
| `latbench.unit.hist.experiment` | 2048 | 2048 of 32 cycles | 64 |

The app runs on `native_sim/native/64` and on `mps2/an385` (Cortex-M3 in
QEMU).

## Known gaps

A test for a known defect or a precondition gap asserts the correct
behavior. While the defect is in the code, the test is an expected
failure:

- In the ztest app, `KNOWN_GAP()` skips the test and prints `KNOWN GAP:`
  with the input and the result. If the result becomes correct, the test
  fails. Then remove `KNOWN_GAP()` from the test.
- In pytest, the test has `xfail(strict=True)`. If the test passes, pytest
  reports a failure. Then remove the marker.

## Run the ztest app

1. Set the environment:

   ```sh
   export ZEPHYR_BASE=/wrk/z/ws-safety/latency-trees/ws-safety/zephyr
   export ZEPHYR_TOOLCHAIN_VARIANT=zephyr
   export ZEPHYR_SDK_INSTALL_DIR=~/zephyr-sdk-1.0.1
   ```

2. Run twister. Put the output folder outside the pinned trees:

   ```sh
   $ZEPHYR_BASE/scripts/twister -T tests/benchmarks/unit/hist \
     -p native_sim/native/64 -p mps2/an385 \
     -x ZEPHYR_MODULES=$ZEPHYR_BASE/../modules/hal/cmsis_6 \
     -O /wrk/z/ws-safety/build-hist-tests/twister-out
   ```

The result is 21 passed and 3 skipped test cases for each scenario. The 3
skipped test cases are the known gaps.

## Run the pytest module

Run pytest from the `scripts` folder:

```sh
cd tests/benchmarks/scripts
python3 -m pytest tests
```

The result is 3 expected failures (`xfailed`) and no failures. The
packages in `scripts/requirements.txt` and `pytest` are necessary.

## Make the fixtures again

Make the fixtures again if you change the output format or the sample
generator `fixture_sample()` in `hist/src/main.c`.

1. Run twister for `native_sim/native/64` (see above).
2. Copy the output of each scenario into its fixture:

   ```sh
   B=/wrk/z/ws-safety/build-hist-tests/twister-out/native_sim_native_64/host_gnu
   for s in fine coarse experiment; do
     $(find $B -path "*latbench.unit.hist.$s/zephyr/zephyr.exe") \
       > tests/benchmarks/scripts/tests/fixtures/hist_$s.log
   done
   ```

3. Run the pytest module.

The round-trip tests in the pytest module make the same samples as the
ztest app. They compare the parsed log with values from these samples.
