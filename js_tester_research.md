# JS Tester Research Notes

> Note by Karl: AI has been used to clarify the notes.

## Project Overview

The autotesting server runs student code in sandboxed environments and reports results back to MarkUs. Each "tester" is a self-contained module that knows how to install its runtime, run tests, and output results in the expected JSON format.

The server lives under `server/autotest_server/`. The testers are under `testers/` inside that.


## How Testers Are Structured

Each tester is a directory with roughly:
- a main tester file (the actual test-running logic)
- a schema file (defines what config options the tester accepts, using `msgspec`)
- a setup file (handles installation and environment creation)
- a system requirements file or requirements file if there are dependencies to install

There are also two base classes defined at the testers root level: one for individual tests and one for the tester itself. Every tester subclasses both.


## Base Classes (what we inherit from)

**`Test` (abstract)**
- `test_name` property must be implemented
- `run()` must be implemented, wrapped with `@Test.run_decorator`
- Result methods: `passed()`, `failed(message)`, `partially_passed(points, message)`, `error(message)`
- The decorator catches exceptions and formats them as error results automatically

**`Tester` (abstract)**
- `run()` must be implemented, wrapped with `@Tester.run_decorator`
- `error_all(message)` - reports an error for all tests at once (useful for install/compile failures)
- Lifecycle hooks: `before_tester_run()`, `after_tester_run()`

---

## Output Format

Everything goes to stdout as JSON strings, one per test:

```json
{
  "name": "test name",
  "output": "message",
  "marks_earned": 1,
  "marks_total": 1,
  "status": "pass",
  "time": 123
}
```

The base class `format()` method handles this. We just call the result methods (`passed()`, `failed()`, etc.) and they return the right JSON.

---

## What Files We Need to Add

1. **Main tester logic** - subclasses `Test` and `Tester`, runs jest, parses output, prints results
2. **Schema definition** - `msgspec.Struct` classes defining what config options the tester accepts (e.g. which test files to run, timeout, etc.)
3. **Setup/install logic** - installs node/npm on the system, creates the environment, returns the schema
4. **A system dependencies file** - shell script or similar to install node via apt-get (same pattern as java uses for openjdk)
5. **An empty `__init__.py`**

---

## Jest JSON Output

Running `jest --json` outputs a JSON blob to stdout. Key structure:

```
testResults[]           <- one entry per test file
  testResults[]         <- one entry per individual test (same key name, confusing)
    fullName            <- "describe block > test name"
    status              <- "passed" | "failed" | "pending"
    failureMessages[]   <- list of strings with stack traces
    duration            <- ms
success                 <- overall pass/fail
numPassedTests
numFailedTests
```

So parsing means: for each suite in `testResults`, iterate its inner `testResults`, create a `JsTest` per entry.

---

## Execution Flow (planned)

1. Get test directory from specs
2. Run `npm install` in that directory (like how java runs `javac` as a compile step)
3. Run `npx jest --json --forceExit`
4. Parse the JSON output
5. For each test result, construct a `JsTest` and print `test.run()`

If `npm install` fails, call `error_all()` and return early. Same if jest produces no output.

---

## Key Questions Still Open

- What config fields does the schema actually need? Java needs `classpath` and `sources_path`. For jest, maybe a path glob to the test files, or a directory? Jest auto-discovers `*.test.js` by default so maybe nothing is needed.
- Do we need a custom `jest.config.js` or can we rely on defaults?
- How does `create_environment` work exactly and what does it need to return? Java just returns the default env dict, py creates a venv. Probably we just return the default for js.
- The setup file has a `settings()` function that returns the schema. Need to wire this up once schema is finalized.

---

## Related Files to Look At

- `testers/tester.py` - base classes, read this first
- `testers/specs.py` - `TestSpecs` wrapper, how specs are accessed
- `testers/schema.py` - `generate_schema()` function, called during install
- `java/` tester - closest analog to what we're building (compile step + run + parse structured output)
- `server/install.py` - how testers get registered and installed
