# Timeout findings, bugs & recommendations

[← back to overview](TIMEOUT-OVERVIEW.md)

## Summary

| # | Layer | Finding | Recommendation |
|---|---|---|---|
| [1](#1-layer-1-jobtimeoutexception-is-silently-absorbed-job-still-reports-finished) | [1](TIMEOUT-RQ-JOB.md) | `JobTimeoutException` caught by bare `except Exception`; job can still report `"finished"`. Unverified. | Catch `JobTimeoutException` explicitly; report as a distinct error; add a test. |
| [2](#2-layer-1-sum-of-all-groups-timeouts-being-0-breaks-the-job-enqueue) | [1](TIMEOUT-RQ-JOB.md) | Sum of all groups' timeouts is `0` (e.g. only group has `timeout: 0`) → job-level `timeout=0` → `rq` rejects the enqueue outright. | Reject/clamp `timeout <= 0` client-side before enqueuing. |
| [3](#3-layer-1-negative-group-timeout-silently-disables-the-job-timeout) | [1](TIMEOUT-RQ-JOB.md) | Negative group `timeout` → negative job timeout → `signal.alarm()` observed to never fire. Layer 1 effectively disabled, no error. Wraparound mechanism unconfirmed. | Reject `timeout < 0` client-side (same validation as row 2). |
| [4](#4-layer-2-blank-test-results-on-a-mid-run-timeout) | [2](TIMEOUT-TEST-GROUP.md) | Every tester but Jupyter shows a blank result table on a mid-run group timeout. | Synthesize an errored test result on `TimeoutExpired`, mirroring `Tester.error_all`. |
| [5](#5-layer-2-pytas-partial-results-are-lost-even-though-it-prints-incrementally) | [2](TIMEOUT-TEST-GROUP.md) | pyta's incremental `print()` has no `flush=True` — results it already produced are lost on SIGKILL anyway. | Add `flush=True` (one-line fix). |
| [6](#6-layer-2-the-did-not-complete-message-is-suppressed-by-any-unrelated-stderr-text) | [2](TIMEOUT-TEST-GROUP.md) | The `"did not complete..."` message is only written for two exact `stderr` shapes — any other stray `stderr` text suppresses it. | Key MarkUs's "timed out" UI off the reliable `timeout` result field, not `stderr` string-matching. |
| [7](#7-layer-3-per-test-timeouts-missing-or-dead-for-most-testers) | [3](TIMEOUT-PER-TEST.md) | Haskell and JS (Jest's own default) have a working per-test timeout. JS's own wrapper and ai attempt one but it's dead code. 6 testers have none; Python has an opt-in, non-schema pattern for C assignments. | Add `test_timeout` schema fields for Python/Java; drop JS's dead wrapper and ai's; generalize `c_helper.py` for Python; defer Racket/R. |
| [8](#8-redis-connectivity-failures) | — | Redis connect timeout can fire before a job even starts; looks like a timeout, isn't one. | Don't conflate with Layer 1/2 reporting; fix is Redis-side. |
| [9](#9-rlimit_cpu-and-oom-kills-bypass-timeoutexpired-entirely) | — | `RLIMIT_CPU`/OOM kills bypass `TimeoutExpired` entirely — no diagnostic message at all. | Detect abnormal termination outside `TimeoutExpired`; document the interaction. |

## Bugs

### 1. Layer 1: `JobTimeoutException` is silently absorbed, job still reports "finished"

#### Finding

`JobTimeoutException(BaseTimeoutException)` subclasses plain `Exception`. Caught bare at two sites:

```python
# server/autotest_server/__init__.py:286-287 (_run_test_specs, per-group loop)
except Exception as e:
    err += "\n\n{}".format(e)
```
- Raw exception text appended to group `stderr`, indistinguishable from any other error.
- Loop continues to the next group with no timeout protection left (alarm already fired).
- Job still completes, reports `"finished"` (`client/autotest_client/__init__.py:282-298`).

```python
# server/autotest_server/__init__.py:415-417 (run_test, outer handler)
except Exception:
    traceback.print_exc()
    error = traceback.format_exc()
```
- `error` field set, but as an opaque traceback, not a labeled timeout.

- Only realistically fires outside normal test execution (file setup, permission changes,
  kill/cleanup stuck) — Layer 2 already caps every group, and this budget is 1.5× the sum of
  all of them. See [firing order](TIMEOUT-OVERVIEW.md#firing-order--scope-order).
- **Status:** inferred from source, not empirically verified.

#### Recommendation

- Catch `rq.timeouts.JobTimeoutException` explicitly, before generic `except Exception`, at both sites.
- Report as a distinct, labeled error, e.g.:
  ```python
  "error": "Autotester infrastructure timeout: job exceeded {N}s"
  ```
- Open question the current fix doesn't answer: re-raise after logging (abort the whole job — matches
  the RQ-level intent of a hard stop) vs. swallow-and-continue to the next group (current behavior,
  unprotected). Just re-labeling the error without deciding this leaves the "no protection for
  remaining groups" half of the bug in place.
- Caveat: `SIGALRM` can technically land at any bytecode boundary, not only inside
  `proc.communicate()`. Explicit catches narrow the common-case window; they don't close it.
- Add a test analogous to `test_timeout.py` that mocks `JobTimeoutException` mid-`_run_test_specs`
  (e.g. `proc.communicate` raising it directly) and asserts on `err` and job status.

### 2. Layer 1: sum of all groups' timeouts being `0` breaks the job enqueue

#### Finding

```python
# client/autotest_client/__init__.py:249-253
timeout = 0
for settings_ in test_settings["testers"]:
    for data in settings_["test_data"]:
        timeout += data["timeout"]  # bracket access — KeyError if a group is missing "timeout"
```
- `BaseTestData.timeout`: no `ge` constraint (external, `markus-autotesting-core`) — `0`/negative
  values pass validation.
- All groups `timeout: 0` → sum `0` → job timeout `int(0 * 1.5) == 0`.
- `rq` rejects this outright:
  ```
  # rq/queue.py:603
  raise ValueError('0 timeout is not allowed. Use -1 for infinite timeout')
  ```
- Uncaught at the client → `PUT /settings/<id>/test` 500s.
- `data["timeout"]` (bracket access, `client/__init__.py:253`) vs. server's
  `test_data.get("timeout")` (`server/autotest_server/__init__.py:245`) — inconsistent hardening;
  a missing `timeout` key raises `KeyError` client-side instead of defaulting.

#### Recommendation

- Real fix belongs upstream: add a `ge=1` (or similar) `Meta` constraint to `BaseTestData.timeout`
  in `markus-autotesting-core`. Closes this and row 3 in one place, at schema-validation time,
  everywhere the schema is used — not just in this one client-side summation loop.
- Stopgap (external dependency, slower to land): reject `timeout <= 0` client-side before
  summing, with a clear validation error instead of a 500. Don't silently clamp — clamping
  changes the instructor's configured value without their knowledge.
- Use `data.get("timeout", <default>)` at `client/autotest_client/__init__.py:253` to match the
  server's defensiveness.

### 3. Layer 1: negative group timeout silently disables the job timeout

#### Finding

- `BaseTestData.timeout`: no `ge` constraint — negative values also pass validation (see above).
- Negative job timeout reaches `rq`'s `UnixSignalDeathPenalty.setup_death_penalty` →
  `signal.alarm(negative_int)`.
- Verified directly (macOS): `signal.alarm(-5)` raises nothing, and the alarm never fires.
  **Mechanism unconfirmed** — plausibly an unsigned wraparound in the C `alarm()` call, but a
  follow-up `signal.alarm(0)` reported 0 remaining, suggesting no alarm was armed at all on this
  platform. Not tested on Linux/glibc (prod). Same caveat as row 1: inferred, not fully verified.
- Unlike `timeout: 0` (row 2 — hard `ValueError`, request 500s), a negative group timeout
  enqueues cleanly and **runs with Layer 1 effectively off**. Silent, not loud.

#### Recommendation

- Same upstream fix as row 2: `ge=1` on `BaseTestData.timeout` closes this too. If only a
  stopgap lands, reject `timeout < 0` client-side via the same validation path.

## Gaps

### 4. Layer 2: blank test results on a mid-run timeout

#### Finding

- Kill message written only to group `stderr`; not surfaced as a test row.
- `stderr` visibility is typically instructor/admin-only, so a timed-out group can show
  **zero test rows** to a student.
- Per-tester behavior on a mid-run hang, verified by reading each `run()`:

| Tester | Behavior | Result on hang |
|---|---|---|
| Python (`server/autotest_server/testers/py/py_tester.py:329-351`) | `run_python_tests()` (329-340) loops over every file and blocks until **all** complete before `run()`'s print loop (343-351) starts | **zero results** |
| Java (`server/autotest_server/testers/java/java_tester.py`, `run()`) | prints only after `run_junit()` returns and JUnit XML is parsed | **zero results** |
| Haskell (`server/autotest_server/testers/haskell/haskell_tester.py:100-139,142-153`) | `run_haskell_tests()` loops over every file internally and blocks until **all** complete before `run()`'s print loop starts — same shape as Python, not per-file | **zero results** |
| Racket (`server/autotest_server/testers/racket/racket_tester.py:54-73,76-93`) | `run_racket_test()` loops over every file internally, blocks until **all** complete, then `run()` prints | **zero results** |
| R (`server/autotest_server/testers/r/r_tester.py:99-124,127-139`) | `run_r_tests()` loops over every file internally, blocks until **all** complete, then `run()` prints | **zero results** |
| JS (`server/autotest_server/testers/js/js_tester.py:103-138`) | prints only after Jest's JSON output is parsed | **zero results** |
| Jupyter (`server/autotest_server/testers/jupyter/jupyter_tester.py:114-125`) | `run()`'s own loop calls `_run_jupyter_tests()` **per notebook file** and prints immediately after each file returns | **partial results survive** — already-completed notebooks before the hanging one |
| pyta (`server/autotest_server/testers/pyta/pyta_tester.py:157`) | prints per test, incrementally, but **without** `flush=True` | **zero results** — see row 5 |

Only Jupyter gets partial credit today; everyone else (including Python) is all-or-nothing.

#### Recommendation

- On `TimeoutExpired`, synthesize a result dict in `_run_test_specs`, matching the field shape
  `Tester.error_all`/`Test.format_result` produce for the same "whole tester died" case
  (`server/autotest_server/testers/tester.py:274-289,45-76`):
  ```python
  # same fields, no "message" key:
  {"name": ..., "output": ..., "marks_earned": ..., "marks_total": ..., "status": ..., "time": ...}
  ```
- **Don't call `Tester.error_all(...)` directly from `_run_test_specs`.** It returns a
  `json.dumps(...)` **string**; `results["tests"]` holds already-parsed **dicts**
  (`loads_partial_json`, `server/autotest_server/utils.py:11`) — appending the string as-is is a
  type mismatch. Either `json.loads()` its output or (cleaner) build the dict directly, matching
  the field shape without importing the `testers` package into server-core code — `_run_test_specs`
  currently has no dependency on `testers.tester` at all; introducing one is a deliberate call,
  not a byproduct of this fix.
- `error_all` defaults `points_total=0` → `0/0`, not `0/N`. Matches existing crash behavior;
  confirm deliberate.
- Include in `results["tests"]` instead of `stderr` — fixes every tester in one place.

### 5. Layer 2: pyta's partial results are lost even though it prints incrementally

#### Finding

- `server/autotest_server/testers/pyta/pyta_tester.py:157`: `print(test.run())` — no `flush=True`.
- Block-buffered to a pipe. On SIGKILL, unflushed buffer contents are discarded, even though the
  print calls already ran for completed tests.
- Distinct root cause from row 4: pyta *attempts* incremental output (like Python and unlike
  Java/Haskell/Racket/R/JS), but loses it to buffering rather than never producing it.

#### Recommendation

- Add `flush=True` at `pyta_tester.py:157` — one-line fix, unrelated to row 4's synthesis fix.

### 6. Layer 2: the "did not complete..." message is suppressed by any unrelated stderr text

#### Finding

```python
# server/autotest_server/__init__.py:278
if err == "Killed\n" or (not err and proc.returncode is not None and proc.returncode != 0):
```
- Only two `err` shapes rewrite `err` to the timeout message: exactly `"Killed\n"`, or empty.
- Any other stray `stderr` (pnpm warning, resolver notice, R library message) → both branches
  false → timeout message never written, original stderr kept as-is.
- Combined with row 4's blank-results gap: student sees an empty group whose only visible
  text is an unrelated warning.
- Mitigation already exists: `timeout_expired = timeout` (`__init__.py:285`) is set
  unconditionally on `TimeoutExpired`, outside this `if` — the result dict's `"timeout"` key
  is reliable even when the `stderr` message isn't written.

#### Recommendation

- Autotester-side (doesn't depend on MarkUs changing anything): unconditionally **append** the
  timeout notice to `err` whenever `timeout_expired` is set, instead of conditionally
  **replacing** `err` only for the two matched shapes. Preserves the tool's own stderr *and*
  guarantees the notice is always present.
- MarkUs-side: key the "timed out" UI off the `timeout` result field, not `stderr`
  string-matching. Not something this repo can guarantee lands — the autotester-side fix above
  doesn't require it.

### 7. Layer 3: per-test timeouts missing or dead for most testers

#### Finding

- Haskell and JS (Jest's own default) have a working per-test timeout.
- JS's own wrapper and ai attempt one via raw uncapped `subprocess.run(timeout=...)`. Layer 2's
  capped, earlier-starting `Popen` always wins in a normal deployment — dead code except when
  Layer 2 is itself unbounded. Mechanism: [TIMEOUT-PER-TEST.md](TIMEOUT-PER-TEST.md).
- Java, Racket, R, Jupyter, custom, pyta: genuinely none (6 testers).
- Python: no schema-level mechanism. `server/autotest_server/testers/py/lib/c_helper.py` already
  gives C-assignment test authors an opt-in per-call timeout (`simple_test`, `_exec`, `_make` —
  `proc.communicate(timeout=...)` + `SIGTERM` via `os.killpg`). Manual, per-call-site, not schema.
- One hang consumes the entire group budget, no finer-grained signal — every tester except
  Haskell and JS.

#### Recommendation

Pattern: `test_timeout`-style field on the tester's `TestData` schema (see
`testers/haskell/schema.py`). Ranked by cost:

| Tester | Fix | Where |
|---|---|---|
| Python | add `pytest-timeout`, pass `--timeout={N}` to `pytest.main(...)`; for C assignments, generalize `c_helper.py` instead of a new mechanism | `_run_pytest_tests`, `server/autotest_server/testers/py/py_tester.py:308-327`. `unittest` path needs signal-alarm/`faulthandler` instead — no equivalent plugin. |
| Java | `--config junit.jupiter.execution.timeout.default={N}s` (caveat below) | `java_command` in `run_junit()`, `server/autotest_server/testers/java/java_tester.py:129-145` |
| JavaScript | drop the dead `subprocess.run(timeout=...)` wrapper, Layer 2 alone governs the group ceiling. Caveat: Jest's own `testTimeout` already works but is overridable via `jest.config`, outside our schema — a new `--testTimeout` field could conflict | `_run_jest`, `server/autotest_server/testers/js/js_tester.py:65-83` |
| ai | drop the dead `subprocess.run(timeout=...)` wrapper — no real per-test mechanism to fall back on | `server/autotest_server/testers/ai/ai_tester.py:71,108` |
| Racket | no native rackunit support; needs `racket/sandbox`'s `call-with-limits` | `racket_tester.py` — larger change |
| R | no native testthat support; `setTimeLimit()`/`R.utils::withTimeout()` unreliable around compiled code | known limitation, not ready-to-implement |

Java caveat: default `timeout.mode=separate_thread` interrupts via a background thread — a
genuinely hung/adversarial test's original thread can leak and keep burning CPU for the rest of
the JVM's life. JUnit just stops waiting on it; the thread doesn't die. Worth a resource-usage
check, given this runs untrusted student code.

Defer Racket/R.

## Related but distinct

### 8. Redis connectivity failures

Not a bug or gap in the timeout layers — documented here because it's easy to mistake for one.

#### Finding

```
File "redis/connection.py", line 1499, in _connect
    sock.connect(socket_address)
TimeoutError: [Errno 110] Connection timed out
...
File "rq/worker/base.py", line 1457, in perform_job
    self.prepare_job_execution(job, remove_from_intermediate_queue)
redis.exceptions.TimeoutError: Timeout connecting to server
```

- **Where:** `prepare_job_execution` — worker opens a fresh Redis connection to record it
  picked up the job, before any test code runs.
- **What it is:** raw TCP-level failure (kernel gave up on `connect`). Not `JobTimeoutException`,
  not `max_test_timeout`, not governed by anything in this doc set.
- **Likely causes** (by frequency): Redis down/restarting/unreachable (network partition,
  firewall/security-group change); `maxclients` exhausted; Redis host overloaded/swapping;
  stale `redis_url` (e.g. after failover).
- **Symptom:** worker failure/crash-looping, not a "timed out" group result.

#### Recommendation

- Don't conflate with [Layer 1](TIMEOUT-RQ-JOB.md) or [Layer 2](TIMEOUT-TEST-GROUP.md) reporting.
- Fix is on the Redis side (availability, capacity, connection string), not autotester timeout logic.

### 9. `RLIMIT_CPU` (and OOM) kills bypass `TimeoutExpired` entirely

Not a timeout mechanism — easily mistaken for one. Worse than row 4's blank-table gap: no
message at all.

#### Finding

- `rlimit_settings` (`README.md:215`) → `get_resource_settings` (`server/autotest_server/utils.py:65-79`)
  → `_rlimit_str2int` (`utils.py:42-43`, `getattr(resource, f"RLIMIT_{name.upper()}")`) — no
  allowlist, `cpu` accepted like any other.
- Baked into the tester command at `server/autotest_server/__init__.py:140`, applied via
  `Tester.set_resource_limits` (`server/autotest_server/testers/tester.py:307-308`) before any
  test runs.
- `RLIMIT_CPU`: CPU time, not wall time. `SIGXCPU` → tester process terminates (default action).
- Signal kill, not `communicate()` timeout → `except subprocess.TimeoutExpired`
  (`server/autotest_server/__init__.py:270-285`) never runs, no `"did not complete..."` message.
- Result: typically empty stdout/stderr, no diagnostic — but not guaranteed empty if the tester
  had already flushed some output before the kill. Same blind spot for OOM kills.

#### Recommendation

- Detect abnormal termination in `_run_test_specs`: nonzero `proc.returncode`, not
  `TimeoutExpired`. Note this is `128 + signum` (e.g. 152 for `SIGXCPU`), **not** Python's raw
  negative-signal convention — `Popen` here runs `shell=True`/bash (`__init__.py:256-266`), so
  the returncode reflects bash's reporting, not the killed child's directly. Don't gate on empty
  output; a partial-output case is possible.
- Document `rlimit_settings`'s interaction with the timeout layers — currently undocumented that
  `RLIMIT_CPU` is a silent failure mode outside all three.

## See also

- [Overview](TIMEOUT-OVERVIEW.md)
- [Layer 1: the RQ job timeout](TIMEOUT-RQ-JOB.md)
- [Layer 2: instructor-configured test-group timeout](TIMEOUT-TEST-GROUP.md)
- [Layer 3: per-test timeouts inside a tester](TIMEOUT-PER-TEST.md)
