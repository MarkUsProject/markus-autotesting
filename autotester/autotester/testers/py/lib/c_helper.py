from collections import defaultdict, OrderedDict
from contextlib import contextmanager
import glob
import locale
import os
import re
import signal
import subprocess
from typing import Optional, List
import unittest


DEFAULT_LTRACE_LOG_FILE = 'ltrace_log.txt'
DEFAULT_GCC_FLAGS = ['-std=gnu99', '-Wall', '-g']
DEFAULT_LTRACE_FLAGS = ['-f', '-n', '2', '-o', DEFAULT_LTRACE_LOG_FILE]

# Note that the keys of the dictionary correspond to the "type" of call it was
regex_dict = OrderedDict(
    resumed='([0-9]+)\s*<\.\.\. (.*) (?:resumed>(.*)=\s)(-?[0-9]+)$',
    unfinished='([0-9]+)\s*(.*)\((.*)<unfinished.*$',
    no_return='([0-9]+)\s*(.*)\((.*)<no return.*$',
    special='([0-9]+)\s*[-+]*\s+(.*)\s*\((.*)\)\s+[-+]*$',
    function_call='([0-9]+)\s*(.*?)\((.*)\).*?=\s+(.+)$'
)


class TestExecutable(unittest.TestCase):
    """A test that compiles and runs a single executable.

    Appropriate for the first few labs, in which we test programs by varying
    inputs (either command-line arguments or stdin), and checking outputs
    on stdout and stderr.
    """
    source_files = []
    executable_name = ''
    make = False
    make_targets = []
    make_args = ['--silent']
    
    @classmethod
    def setUpClass(cls) -> None:
        """Compile the program, storing stdout and stderr of compilation.

        First remove any .o files and the executable file

        Use make if cls.make is True, and gcc otherwise.
        """
        if not cls.make and not cls.source_files:
            raise ValueError(
                'ERROR: TestExecutable subclasses must specify source_files or set make=True.')

        cls.compile_out = ''
        cls.compile_err = ''

        # Default executable name is based on the first source file.
        if not cls.make and not cls.executable_name:
            if isinstance(cls.source_files, list):
                first_file = cls.source_files[0]
            else:  # cls.source_files is a string
                first_file = cls.source_files
            cls.executable_name = os.path.splitext(os.path.basename(first_file))[0]

        try:
            if cls.make:
                # Tuple (stdoutdata, stderrdata) is returned
                cls.compile_out, cls.compile_err, _ = _make(cls.make_targets, cls.make_args)
            else:
                cls.compile_out, cls.compile_err, _ = _compile(cls.source_files, cls.executable_name)
        except subprocess.CalledProcessError:
            cls.compiled = False
        else:
            cls.compiled = True


    def setUp(self) -> None:
        """If the compilation was not successful, automatically fail every test.
        """
        if not self.compiled:
            self.fail('Test did not run due to a compilation error.')

    def _check_compiler_warnings(self) -> None:
        """Assert that compilation occurred without errors or warnings.
        """
        self.assertEqual(self.compile_out, '')
        self.assertEqual(self.compile_err, '')

    def _run_exec(self, args: Optional[List[str]] = None, **kwargs) -> None:
        """Run this test class' executable with the given arguments and options."""
        return _exec([os.path.join('.', self.executable_name)] + (args or []),
                     **kwargs)


def simple_run(args: List[str], **kwargs):
    """Create a unittest test for fixed command-line arguments, expected stdout and stderr.

    input_ optionally specifies the (string) contents of stdin.
    Returns a function which takes an object on which to call run_exec (hence this object must
    be a subclass of TestExecutable).
    """
    def _t(self: 'TestExecutable') -> None:
        self._run_exec(args=args, **kwargs)

    return _t


def simple_test(args: List[str], expected_stdout='', *, expected_stderr='', expected_status=0, input_=None, timeout=2, check=True, rstrip=False, doc='', stderr_relax=False):
    """Create a unittest test for fixed command-line arguments, expected stdout and stderr, and exit status.

    If rstrip is True, ignore trailing whitespace when doing text comparison.

    If expected_stdout, expected_stderr, or expected_status are None, don't test.

    doc specifies the docstring of the test function.

    If stderr_relax is True, look for the expected stderr in stdout
    (as a substring check) in addition to in stderr, passing the test if
    one of these succeeds.
    """
    def _t(self: 'TestExecutable') -> None:
        stdout, stderr, returncode = self._run_exec(args=args, input_=input_, timeout=timeout, check=check)

        nonlocal expected_stderr
        nonlocal expected_stdout

        if rstrip:
            stdout = stdout.rstrip()
            stderr = stderr.rstrip()
            if expected_stderr is not None:
                expected_stderr = expected_stderr.rstrip()
            if expected_stdout is not None:
                expected_stdout = expected_stdout.rstrip()

        if expected_stderr is not None:
            if stderr_relax:
                try:
                    self.assertIn(expected_stderr, stdout)
                except AssertionError:
                    self.assertEqual(stderr, expected_stderr)
            else:
                self.assertEqual(stderr, expected_stderr)

        if expected_stdout is not None:
            self.assertEqual(stdout, expected_stdout)

        if expected_status is not None:
            self.assertEqual(returncode, expected_status)

    _t.__doc__ = doc
    return _t

def substr_test(args: List[str], expected_stdout='', *, expected_stderr='', expected_status=0, input_=None, timeout=2, check=True, doc=''):
    """Create a unittest test for fixed command-line arguments, expected stdout and stderr, and exit status.

    This test is more lenient that simple_test because it looks for expected
    output as a substring of the actual output.
    If rstrip is True, ignore trailing whitespace when doing text comparison.

    If expected_stdout, expected_stderr, or expected_status are None, don't test.

    doc specifies the docstring of the test function.
    """
    def _t(self: 'TestExecutable') -> None:
        stdout, stderr, returncode = self._run_exec(args=args, input_=input_, timeout=timeout, check=check)

        nonlocal expected_stderr
        nonlocal expected_stdout

        if expected_stderr is not None:
            self.assertIn(expected_stderr.rstrip(), stderr)

        if expected_stdout is not None:
            self.assertIn(expected_stdout.rstrip(), stdout)

        if expected_status is not None:
            self.assertEqual(returncode, expected_status)

    _t.__doc__ = doc
    return _t

class TestTrace(TestExecutable):
    """Test class to support checks with ltrace.

    This can be thought of as the basic class for testing traces
    (as TestExecutable is used for simple I/O comparison,
    TestTrace is used for simple trace parsing).

    This is the "Builder" for Trace objects. It is the preferred way of constructing
    a Trace object, since it helps parse any additional arguments to ltrace
    args is a list of string arguments
    """
    call_types = [] # The only call types to watch out for (see ltrace man page)

    @classmethod
    def _check_trace(cls, args: Optional[List[str]] = None, ltrace_flags=None, **kwargs):
        if ltrace_flags is None:
            ltrace_flags = DEFAULT_LTRACE_FLAGS
        else:
            ltrace_flags = DEFAULT_LTRACE_FLAGS + ltrace_flags
        if cls.call_types:
            ltrace_flags = ltrace_flags + ['-e', '+'.join(['__libc_start_main'] + cls.call_types)]

        return Trace([os.path.join('.', cls.executable_name)] + (args or []),
                     ltrace_flags, **kwargs)


class Trace:
    """Class representing the result of a run of ltrace.

    Parses a trace into a process_log: a data structure tracking process ids and their calls.
    API: process_log is a dict with keys representing PIDs (string),
    and the values are a list of "function call tuple" made by PID, as specified by ltrace
    a function call tuple has the form (func_name, args, ret_val, type).
    Note that we can also view the dictionary as being constructed from these arity 5-tuples, namely:
    (PID, func_name, args, ret_val, type)
    Note that args is "junk" and needs some postprocessing (for example, splitting on ,) This was done because
    parsing is a better approach when dealing with variable-number capture groups, as there will be with arguments to a function.
    Note that for those that do not have certain fields, like ret_val for unfinished, we pad with None. However, the last
    element of the tuple (tuple[-1]) is always the "type" of the call, as determined by the regex that classified it.
    Note 2: the "special" regex is a special case, corresponding to things like:
    --- SIGPIPE (Broken pipe) ---
    and
    +++ exited (status 1) +++
    Hence, it is not obvious how retval, args and such fit in.
    We define the following convention:
    (1,2,3,4,"special") where
    1 is the PID
    2 is the "function name" (SIGPIPE, exited)
    3 is the "arguments" (anything inside the brackets)
    4 is None (padding)
    this can be confirmed examining the regex
    """

    def __init__(self, command: List[str], ltrace_flags: Optional[List[str]] = None, **kwargs):
        ltrace_flags = ltrace_flags or []
        try:
            _exec(['ltrace'] + ltrace_flags + command, **kwargs)
        except subprocess.TimeoutExpired:  # allow for partial results to be reported
            pass

        with open(DEFAULT_LTRACE_LOG_FILE, 'rb') as f:
            f_bytes = f.read()
            self.raw = f_bytes.decode(errors='ignore')

        self.parent_first_process = None
        self.lines = []
        self.process_log = defaultdict(list)
        self.first_process = None
        self.split_lines = self.raw.splitlines()
        if len(self.split_lines) > 1:
            parsed_line = parse_arbitrary(self.split_lines[0], r'([0-9]+)\s*.')
            if parsed_line:
                self.first_process = parsed_line[0]
            else:
                raise Exception("First call of ltrace is not pid!")

        for line in self.split_lines:
            parsed_line = run_through_regexes(regex_dict, line)
            if len(parsed_line) < 4 or not parsed_line[0]:
                continue
            pid = parsed_line[0]
            self.lines.append(parsed_line)
            self.process_log[pid].append(list(parsed_line[1:]))

    def get_status(self, pid):
        """Return the exit status recorded in this trace for the given pid."""
        if pid not in self.process_log:
            return None

        for calls in self.process_log[pid]:
            if 'exited' in calls[0]:
                return int(calls[1].split()[-1])

    def lines_for_pid(self, pid, match=''):
        """Return the lines in this trace for the given pid.

        If match is not-empty, only return the lines whose function names
        match the given expression.

        Right now only does literal matching, but eventually could support regex.
        """
        if pid not in self.process_log:
            return []

        if not match:
            return self.process_log[pid]

        return [call for call in self.process_log[pid]
                if call[0] == match]


def run_through_regexes(regexes, trace_line):
    """Parse trace_line against the collection of regexes.
    """
    for key, regex in regexes.items():
        parser = re.compile(regex)
        result = parser.match(trace_line)
        if not result:
            continue

        final_result = list(result.groups())

        # Note that this check is unnecessary, because an optional capturing group will return None if it
        # is not detected
        if len(final_result) >= 3:
            # print("this is the len of final result " + str(len(final_result)))
            # print(final_result)
            # clean the line before putting it in
            sep = '->'
            rest = final_result[1].split(sep, 1)
            if len(rest) > 1: #in case there were multiple
                final_result[1] = rest[1]
            # print(final_result)
        else:
            raise ValueError("groups mismatch arity")

        while len(final_result) < 4:
            final_result+=(None,)

        final_result += (key,) # append the type of the entry to the end
        return final_result # stops as soon as a matching regex is encountered
    # print("line did not have any mathces " + trace_line)
    return ('','','','') # did not match with any of the regexes


def parse_arbitrary(trace_line, regex):
    """Apply the regex to the string, returning the matching groups (if any).

    trace_line and regex are both strings.
    """
    parser = re.compile(regex)
    result = parser.match(trace_line)
    if result:
        return result.groups()


class TestGenerator:
    """Generate a set of test files given a solution executable and input set.

    It can take in the input files, run them through a correct instance
    of the program and then generate the correct output files. You can then
    use these output files to test against a run of the student program.

    To do this, please see a2_fs.py for details. But essentially, you call convert_inputs,
    convert_outputs, convert_errors IN THIS ORDER to populate a dict_of_tests.
    The convert functions require the solution executable to already to be built.

    Note: silent failures can happen (e.g., if the executable is not found).
    """
    dict_of_tests = defaultdict(list)
    # TODO add support for command-line arguments

    def __init__(self,
                 input_dir=None,
                 executable_path=None,
                 out_dir=None,
                 input_extension='txt',
                 output_extension='stdout',
                 error_extension='stderr'):
        """
        `input_dir` specifies where the input files are found
        The extensions specify a pattern to look for in target files
        `out_dir` specifies where the output files should go
        (currently, standard output and standard error files must go to the
        same directory)
        `executable_path` specifies where the executable may be found
        """
        self.executable_path = executable_path
        self.input_dir = input_dir
        self.out_dir = out_dir
        self.input_extension = input_extension
        self.output_extension = output_extension
        self.error_extension = error_extension

    def build_outputs(self, args=''):
        """Generate all output files.

        `arg`s is optionally a string containing the command-line arguments given to the executable.
        """
        print(os.path.join(self.input_dir, '*.' + self.input_extension))
        for file in glob.glob(os.path.join(self.input_dir, '*.' + self.input_extension)):
            print(file)
            name = os.path.splitext(os.path.basename(file))[0]
            stdout_file = os.path.join(self.out_dir, name + '.' + self.output_extension)
            stderr_file = os.path.join(self.out_dir, name + '.' + self.error_extension)
            cmd = "{} {} < {} > {} 2> {}".format(self.executable_path, args, file, stdout_file, stderr_file)
            print('Running:', cmd)
            try:
                _exec_shell([cmd])
            except subprocess.TimeoutExpired:     # TODO add handling for TimeoutExpired (error log file for example?)
                print("failed on {}".format(file))

    def clean(self):
        """Remove generated test files."""
        for file in glob.glob(os.path.join(self.input_dir, '*.' + self.input_extension)):
            name = os.path.splitext(os.path.basename(file))[0]
            stdout_file = os.path.join(self.out_dir, name + '.' + self.output_extension)
            stderr_file = os.path.join(self.out_dir, name + '.' + self.error_extension)
            os.remove(stdout_file)
            os.remove(stderr_file)

    def populate_tests(self, test_klass, args=None):
        """Add test methods to `test_klass` from the generated test files.

        This must be called *after* build_outputs has been called.
        """
        args = args or []
        for file in glob.glob(os.path.join(self.input_dir, '*.' + self.input_extension)):
            name = os.path.splitext(os.path.basename(file))[0]
            stdout_file = os.path.join(self.out_dir, name + '.' + self.output_extension)
            stderr_file = os.path.join(self.out_dir, name + '.' + self.error_extension)
            with open(file) as in_, open(stdout_file) as out, open(stderr_file) as err:
                test_in = in_.read()
                test_out = out.read()
                test_err = err.read()

            setattr(test_klass, 'test_' + name,
                    simple_test(args, test_out, test_err, test_in))


def _compile(files, exec_name=None, gcc_flags=DEFAULT_GCC_FLAGS, **kwargs):
    """Run gcc with the given flags on the given files."""
    if isinstance(files, str):
        files = [files]
    args = ['gcc'] + gcc_flags
    if exec_name:
        args += ['-o', exec_name]
    return _exec(args + files, **kwargs)


def _make(targets=None, make_args=['--silent'], **kwargs):
    """Run make on the given targets."""
    return _exec(['make'] + make_args + (targets or []), timeout=60, **kwargs)


def _exec(args, *, input_=None, timeout=10, check=True, shell=False):
    """Wrapper function that calls exec on the given args in a new subprocess.

    Return a triple (stdout, stderr, exit status) from the subprocess.
    Raise an exception on subprocess timeout.

    Note that args should be a list of strings.

    NOTE: This function breaks on Windows; it accesses a specific version of the os module.
    """
    proc = subprocess.Popen(
        args,  # essentially, creates a new pipe
        stdin=subprocess.PIPE,  # specifies the file descriptor for std in #set stdin as the pipe to the standard stream
        stdout=subprocess.PIPE,  # this allows proc.stdout to be used as the stdin for a new process
        stderr=subprocess.PIPE,
        encoding=locale.getpreferredencoding(False),
        preexec_fn=lambda: os.setsid(),
        shell=shell)

    try:
        stdout, stderr = proc.communicate(timeout=timeout, input=input_)
        return stdout, stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        raise e from e


@contextmanager
def ongoing_process(args, check_killed=True):
    """Create a context manager for a non-terminating process.

    Used to test servers.

    If check_killed is True, the exit status of the process is checked
    to determine if the server was killed. (If it wasn't, it may have
    exited with a segmentation fault earlier than expected.)
    """
    proc = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding=locale.getpreferredencoding(False),
    )
    try:
        yield proc
    except Exception as e:
        proc.exception = e
    else:
        proc.exception = None
    finally:
        proc.kill()
        proc.stdout, proc.stderr = proc.communicate()

    if proc.exception:
        raise proc.exception

    if check_killed:
        assert proc.returncode == -9, 'server exited abnormally'


def _exec_shell(args, *, input_=None, timeout=1, check=True):
    """Wrapper function that calls exec on the given args in a new subprocess with a shell.

    Returns a communicate method (like a pipe) to the exec process.
    Raises an exception on subprocess timeout.

    Note that args should be a list of strings.

    In the future, consider merging this back with _exec and retroupdating existing uses
    """
    proc = subprocess.Popen(
        args,  # essentially, creates a new pipe
        stdin=subprocess.PIPE,  # specifies the file descriptor for std in #set stdin as the pipe to the standard stream
        stdout=subprocess.PIPE,  # this allows proc.stdout to be used as the stdin for a new process
        stderr=subprocess.PIPE,
        encoding=locale.getpreferredencoding(False),
        preexec_fn=lambda: os.setsid(),
        shell=True)
    try:
        return proc.communicate(timeout=timeout, input=input_)
    except subprocess.TimeoutExpired as e:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        raise e from e
