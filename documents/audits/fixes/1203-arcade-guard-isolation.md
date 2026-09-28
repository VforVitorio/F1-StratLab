# #1203 arcade guard isolation

Issue #1203 tracks two arcade test guards that were reported to fail in the
full serial suite while passing in isolation. The issue is about test
isolation and clean stream shutdown, not a change to the arcade loader or
telemetry payload contract.

## Findings

- The source-inspection guard was already made independent of live monkeypatches
  by PR #1230. It reads `src/arcade/data.py` from disk.
- The reported telemetry `TypeError` did not reproduce after the #1202 test
  timing fix. The reproducible pollution mechanism was daemon test workers
  left alive across tests.
- The arcade test suite also imports Pyglet. On Windows, its unused input and
  audio backends can leave process-wide workers active during interpreter
  teardown.
- The stream accept loop now uses a bounded poll timeout so `stop()` can end it
  on every supported platform. A closed client socket during shutdown is a
  normal exit path.

## Change

- Test-created stream workers are retained, stopped, joined, and checked at
  the test boundary.
- Real-server helpers retain both the accept and send workers, wait for the
  client workers they create, and release the slow consumer gate from
  `finally` before teardown.
- The wire-contract helper performs the same cleanup even when its assertion
  path raises.
- The stream scheduling test waits for the worker's eventual execution and
  no longer asserts an invalid immediate ordering guarantee.
- Windows tests select silent Pyglet audio and disable unused XInput polling.

## Verification

- Focused arcade guards and worker tests: 36 passed.
- Full serial suite: 1454 passed, 4 skipped, 72 deselected, 29 warnings.
- Full xdist suite: 1454 passed, 4 skipped, 29 warnings.
- Ruff check, Ruff format check, scoped mypy, and `git diff --check`: passed.

The four skips are optional packages absent from the local environment:
`setfit`, `pydub`, `edge_tts`, and `streamlit`.
