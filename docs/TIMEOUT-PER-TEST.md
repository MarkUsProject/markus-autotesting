# Layer 3: per-test timeouts inside a tester

[← back to overview](TIMEOUT-OVERVIEW.md)

## What it is

- Timeout enforced inside the tester process, scoped to a single test (not the whole group).
- [Layer 1](TIMEOUT-RQ-JOB.md) and [Layer 2](TIMEOUT-TEST-GROUP.md) both operate at the
  test-*group* level or above.
- 2 real: Haskell, JS (Jest's own default). 2 dead-code attempts: JS's own outer wrapper, ai.
  6 none: Java, Racket, R, Jupyter, custom, pyta. Python: none at tester level, but see the
  `c_helper.py` row below.

| Tester | Per-test timeout? | Mechanism |
|---|---|---|
| Haskell | yes | `test_timeout` (`server/autotest_server/testers/haskell/schema.py:20`, default 10s) → `--timeout={N}s` to `tasty-discover` (`server/autotest_server/testers/haskell/haskell_tester.py:75`) |
| JavaScript | yes, **and** dead code | Jest's own `testTimeout` (default 5000ms): real, per-test, independent of Layer 2. Config outside our schema — `--rootDir` picks up any `jest.config`/`package.json:jest` in the test dir. Separately: `_run_jest`'s `subprocess.run(timeout=timeout)` (`server/autotest_server/testers/js/js_tester.py:65-83`, kwarg at line 81) — raw uncapped group timeout, Layer 2 always fires first, caller's `TestError("Jest timed out")` (`js_tester.py:121-122`) dead code |
| Python | none (tester-level) | pytest/unittest in-process; one hang consumes the full group budget. Opt-in per-call timeout for C-assignment test authors: `simple_test`/`_exec`, `server/autotest_server/testers/py/lib/c_helper.py:109,470,491` (`proc.communicate(timeout=...)`, `SIGTERM` via `os.killpg`) — not a schema field, not automatic. |
| Java | none | JUnit console launcher — no timeout configured |
| Racket | none | `subprocess.run`, group timeout only |
| R | none | `subprocess.run`, group timeout only |
| Jupyter | none | group timeout only |
| ai | dead code | `ai_tester.py:71,108` — same pattern as JS's wrapper: raw uncapped group `timeout` passed to `subprocess.run`, Layer 2 always fires first, no real internal equivalent |
| custom | none | `custom_tester.py` — `subprocess.run` with no timeout argument at all |
| pyta | none | `pyta_tester.py` — no timeout mechanism anywhere in the file |

## See also

- [Overview](TIMEOUT-OVERVIEW.md)
- [Layer 1: the RQ job timeout](TIMEOUT-RQ-JOB.md)
- [Layer 2: instructor-configured test-group timeout](TIMEOUT-TEST-GROUP.md)
- [Findings, bugs & recommendations](TIMEOUT-FINDINGS.md)
