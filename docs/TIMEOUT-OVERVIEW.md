# Timeouts

| Layer | Scope | Set by | Doc |
|---|---|---|---|
| [1](#layer-1-the-rq-job-timeout-infra-wide-separate-from-redis) | whole RQ job | `1.5 × sum` of group timeouts, client-computed | [§ Layer 1](#layer-1-the-rq-job-timeout-infra-wide-separate-from-redis) |
| [2](#layer-2-instructor-configured-test-group-timeout) | one test group | instructor, capped by `max_test_timeout` | [§ Layer 2](#layer-2-instructor-configured-test-group-timeout) |
| [3](#layer-3-per-test-timeouts-inside-a-tester) | one test | tester-specific; Haskell and JS (Jest-internal) work, JS's own wrapper and ai are dead code, 6 have none | [§ Layer 3](#layer-3-per-test-timeouts-inside-a-tester) |


```
RQ job timeout                 (Layer 1, whole job)
        │
        ▼
instructor test-group timeout  (Layer 2, per test group)
        │
        ▼
in-tester per-test timeout     (Layer 3, per individual test)
```

## Firing order ≠ scope order

- **Scope order** (broadest → narrowest): Layer 1 → Layer 2 → Layer 3.
- **Firing order** (common case): narrowest *working* layer fires first — Layer 3 (Haskell, JS's
  Jest-internal timeout), then Layer 2. JS's own wrapper and ai's are dead code
  (see [§ Layer 3](#layer-3-per-test-timeouts-inside-a-tester)) — Layer 2 fires first for those regardless.
- Layer 1's budget is deliberately generous (table above) — normal Layer 2 timeouts never reach it.
- Layer 1 firing at all is unusual: every group ran to its own timeout, or something outside
  normal test execution hung (file setup, permission changes, Layer 2's kill/cleanup).
  Least clearly reported case — see the known issues linked from
  [§ Layer 1](#layer-1-the-rq-job-timeout-infra-wide-separate-from-redis).

## Layer 1: the RQ job timeout (infra-wide, separate from Redis)

### What it is

- Timeout `rq` (job queue library, backed by Redis) applies to the whole worker job.
- Not a Redis timeout. Not a server config.

### Set by

Client (`client/`), at enqueue time, in `run_tests()`:

```python
# client/autotest_client/__init__.py:249-277
timeout = 0
for settings_ in test_settings["testers"]:
    for data in settings_["test_data"]:
        timeout += data["timeout"]
...
queue.enqueue_call(
    "autotest_server.run_test",
    ...
    timeout=int(timeout * 1.5),
    ...
)
```

- `timeout = 1.5 × sum` of every test group's timeout in the settings.
- Sums *all* groups in settings, not just categories being run — generous ceiling.
- `data["timeout"]` (line 253): raw instructor value, bracket access (`KeyError` if missing).
  Client has no visibility into `max_test_timeout` ([Layer 2](#layer-2-instructor-configured-test-group-timeout), server-side
  only) — sum is uncapped.
- `sum == 0` (e.g. only group has `timeout: 0`) → `rq` rejects the enqueue outright. `sum < 0`
  (negative group timeout) → enqueues cleanly, Layer 1 silently disabled. Neither is validated
  here.
- Related: `SETTINGS_JOB_TIMEOUT` (client env var, default 1200s, `README.md:276`) —
  caps the settings-update job, not test runs.

### Enforced by

`UnixSignalDeathPenalty` (`rq/timeouts.py`) — `SIGALRM` in the worker's "horse" process:

```python
class JobTimeoutException(BaseTimeoutException):
    """Raised when a job takes longer to complete than the allowed maximum
    timeout value."""
```

### On expiry

- `JobTimeoutException` raised: `"Task exceeded maximum timeout value ({N} seconds)"`.
- Handling depends on where it's raised.

## Layer 2: instructor-configured test-group timeout

### What it is

- Per-group (not per-test) `timeout` field.
- Defined once for all testers in `markus-autotesting-core`'s `BaseTestData`
  (external dependency — not vendored in this repo):

```python
timeout: Annotated[int, Meta(title="Timeout")] = 30
"""The timeout in seconds for this test group."""
```

- Default 30s.

### Set by

- Instructor, via the field above.
- Capped server-wide by `max_test_timeout` (`server/autotest_server/settings.yml:8`,
  default `3600`, `README.md:209-211`):

```python
# __init__.py:246-251
max_timeout = config.get("max_test_timeout")
if max_timeout is not None:
    if timeout is None:
        timeout = max_timeout
    else:
        timeout = min(timeout, max_timeout)
```

- No group timeout *and* no `max_test_timeout` → subprocess timeout `None` (unbounded).
  See `test_timeout_none_passes_through_when_max_not_configured`
  (`server/autotest_server/tests/test_timeout.py`).

### Enforced by

- `_run_test_specs`, `server/autotest_server/__init__.py:218-296`.
- One subprocess per group (whole tester process — JUnit run, pytest run, etc.,
  not one subprocess per test).
- `Popen.communicate(timeout=...)` (`__init__.py:269`).

### On expiry

```python
# __init__.py:267-285, condensed
try:
    out, err = proc.communicate(timeout=timeout)              # :269
except subprocess.TimeoutExpired:
    kill(proc)                                                 # _kill_user_processes (prod, sudo) /
                                                                # _kill_pgid_children (dev)
    out, err = proc.communicate()                              # drain remaining output
    if err == "Killed\n" or (not err and proc.returncode not in (None, 0)):
        err = f"Tests for {group_name} did not complete within time limit ({timeout}s)"
        # unnamed variant if no extra_info.name
    # else: any other stderr text (e.g. a tool warning) → err left as-is, message
    # NOT written — known reporting gap, see linked issues
    timeout_expired = timeout                                  # :285
# else: timeout_expired stays None

result = {..., "timeout": timeout_expired, "stderr": err, ...}  # _create_test_group_result, :61-93,295
```

Distinct from an OOM/`RLIMIT_CPU` kill that happens *before* the timeout — that never reaches
this `except` block at all.

Spec: `server/autotest_server/tests/test_timeout.py`
(`TestMaxTestTimeout`, `TestTimeoutKillHandler`).

## Layer 3: per-test timeouts inside a tester

### What it is

- Timeout enforced inside the tester process, scoped to a single test (not the whole group).
- [Layer 1](#layer-1-the-rq-job-timeout-infra-wide-separate-from-redis) and [Layer 2](#layer-2-instructor-configured-test-group-timeout) both operate at the
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

## Related, not a bug

Failure modes that look like a timeout but aren't one of the three layers above — no fix belongs
in this repo, but worth knowing so they don't get mistaken for a Layer 1/2/3 issue.

### Redis connectivity failures

```
File "redis/connection.py", line 1499, in _connect
    sock.connect(socket_address)
TimeoutError: [Errno 110] Connection timed out
...
File "rq/worker/base.py", line 1457, in perform_job
    self.prepare_job_execution(job, remove_from_intermediate_queue)
redis.exceptions.TimeoutError: Timeout connecting to server
```

- `prepare_job_execution` — worker opens a fresh Redis connection to record it picked up the job,
  before any test code runs.
- Raw TCP-level failure (kernel gave up on `connect`). Not `JobTimeoutException`, not
  `max_test_timeout`.
- Causes: Redis down/restarting/unreachable, `maxclients` exhausted, Redis host
  overloaded/swapping, stale `redis_url` (e.g. after failover).
- Symptom: worker failure/crash-looping, not a "timed out" group result.
- Fix is Redis-side (availability, capacity, connection string) — not autotester timeout logic.

## See also

- `README.md` — `max_test_timeout`, `SETTINGS_JOB_TIMEOUT`, `rlimit_settings`
- `server/autotest_server/tests/test_timeout.py` — Layer 2 cap/kill spec
