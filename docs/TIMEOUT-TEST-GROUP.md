# Layer 2: instructor-configured test-group timeout

[← back to overview](TIMEOUT-OVERVIEW.md)

## What it is

- Per-group (not per-test) `timeout` field.
- Defined once for all testers in `markus-autotesting-core`'s `BaseTestData`
  (external dependency — not vendored in this repo):

```python
timeout: Annotated[int, Meta(title="Timeout")] = 30
"""The timeout in seconds for this test group."""
```

- Default 30s.

## Set by

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

## Enforced by

- `_run_test_specs`, `server/autotest_server/__init__.py:218-296`.
- One subprocess per group (whole tester process — JUnit run, pytest run, etc.,
  not one subprocess per test).
- `Popen.communicate(timeout=...)` (`__init__.py:269`).

## On expiry

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
    # NOT written — see Findings for this gap and its mitigation
    timeout_expired = timeout                                  # :285
# else: timeout_expired stays None

result = {..., "timeout": timeout_expired, "stderr": err, ...}  # _create_test_group_result, :61-93,295
```

Distinct from an OOM/`RLIMIT_CPU` kill that happens *before* the timeout — that never reaches
this `except` block at all ([Findings](TIMEOUT-FINDINGS.md)).

Spec: `server/autotest_server/tests/test_timeout.py`
(`TestMaxTestTimeout`, `TestTimeoutKillHandler`).

## See also

- [Overview](TIMEOUT-OVERVIEW.md)
- [Layer 1: the RQ job timeout](TIMEOUT-RQ-JOB.md)
- [Layer 3: per-test timeouts inside a tester](TIMEOUT-PER-TEST.md)
- [Findings, bugs & recommendations](TIMEOUT-FINDINGS.md)
- `server/autotest_server/tests/test_timeout.py`
