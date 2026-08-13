# Timeouts

| Layer | Scope | Set by | Doc |
|---|---|---|---|
| [1](TIMEOUT-RQ-JOB.md) | whole RQ job | `1.5 × sum` of group timeouts, client-computed | [TIMEOUT-RQ-JOB.md](TIMEOUT-RQ-JOB.md) |
| [2](TIMEOUT-TEST-GROUP.md) | one test group | instructor, capped by `max_test_timeout` | [TIMEOUT-TEST-GROUP.md](TIMEOUT-TEST-GROUP.md) |
| [3](TIMEOUT-PER-TEST.md) | one test | tester-specific; Haskell and JS (Jest-internal) work, JS's own wrapper and ai are dead code, 6 have none | [TIMEOUT-PER-TEST.md](TIMEOUT-PER-TEST.md) |


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
  ([Findings](TIMEOUT-FINDINGS.md)) — Layer 2 fires first for those regardless.
- Layer 1's budget is deliberately generous (table above) — normal Layer 2 timeouts never reach it.
- Layer 1 firing at all is unusual: every group ran to its own timeout, or something outside
  normal test execution hung (file setup, permission changes, Layer 2's kill/cleanup).
  Least clearly reported case — see
  [Layer 1 finding](TIMEOUT-FINDINGS.md#1-layer-1-jobtimeoutexception-is-silently-absorbed-job-still-reports-finished).

## See also

- [Findings, bugs & recommendations](TIMEOUT-FINDINGS.md) — includes Redis connectivity
  failures and `RLIMIT_CPU`/OOM kills (neither is one of these three layers)
- `README.md` — `max_test_timeout`, `SETTINGS_JOB_TIMEOUT`
- `server/autotest_server/tests/test_timeout.py` — Layer 2 cap/kill spec
