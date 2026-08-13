# Layer 1: the RQ job timeout (infra-wide, separate from Redis)

[← back to overview](TIMEOUT-OVERVIEW.md)

## What it is

- Timeout `rq` (job queue library, backed by Redis) applies to the whole worker job.
- Not a Redis timeout. Not a server config.

## Set by

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
  Client has no visibility into `max_test_timeout` ([Layer 2](TIMEOUT-TEST-GROUP.md), server-side
  only) — sum is uncapped. See [Findings](TIMEOUT-FINDINGS.md).
- `sum == 0` (e.g. only group has `timeout: 0`) → `rq` rejects the enqueue outright. `sum < 0`
  (negative group timeout) → enqueues cleanly, Layer 1 silently disabled. Neither is validated
  here. See [Findings](TIMEOUT-FINDINGS.md).
- Related: `SETTINGS_JOB_TIMEOUT` (client env var, default 1200s, `README.md:276`) —
  caps the settings-update job, not test runs.

## Enforced by

`UnixSignalDeathPenalty` (`rq/timeouts.py`) — `SIGALRM` in the worker's "horse" process:

```python
class JobTimeoutException(BaseTimeoutException):
    """Raised when a job takes longer to complete than the allowed maximum
    timeout value."""
```

## On expiry

- `JobTimeoutException` raised: `"Task exceeded maximum timeout value ({N} seconds)"`.
- Handling depends on where it's raised — see [Findings](TIMEOUT-FINDINGS.md).

## See also

- [Overview](TIMEOUT-OVERVIEW.md)
- [Layer 2: instructor-configured test-group timeout](TIMEOUT-TEST-GROUP.md)
- [Layer 3: per-test timeouts inside a tester](TIMEOUT-PER-TEST.md)
- [Findings, bugs & recommendations](TIMEOUT-FINDINGS.md)
