"""
This module contains the Hooks class which is used to load and run 
hooks defined in buitin_hooks.py, a custom hooks file and all
default_hooks.py files in testers/testers/*/bin directories. 
"""

import os
import traceback
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import contextmanager
from autotester.server.hooks_context import builtin_hooks
from autotester.server.utils.path_management import current_directory, add_path


class Hooks:
    """
    The hooks class is used to load and run all hooks that may be used while running tests.

    Loads three types of hooks:
        - custom hooks: hook functions contained in a user created file python file.
        - builtin hooks: hook functions contained in builtin_hooks.py
        - default hooks: hook functions contained in any default_hooks.py file in tester bin/ 
                         directories.

    For default and custom hooks, the name of the hook function indicates when each hook should
    be run relative to the code contained in the self.around context manager. 
    For example, a function named 'before_all' will be run before a block of code (when 
    tester_type=='all'), a function named 'after_each' will be run after a block (when
    tester_type=='each'), a function named 'before_all_racket' will be run before a block of code
    (when tester_type=='racket'). 

    Acceptable hook names are (in execution order):
        before_all
        before_all_X
        before_each_X
        before_each
        after_each
        after_each_X
        after_all_X
        after_all

    where X is the name of a tester (eg. 'racket', 'py', etc.).

    Builtin hooks can have any name and when they are executed is instead determined by the values
    associated to their name in the builtin_hooks.HOOKS dictionary.  
    """
    HOOK_BASENAMES = ['before_all', 'before_each', 'after_all', 'after_each']

    def __init__(self, custom_hooks_path=None, testers=None, cwd=None, args=None, kwargs=None):
        """
        Create a new Hooks object instance with args:

        custom_hooks_path: is a path to a file containing custom hooks 
                           (see doc/hooks.py for an example)
        testers: a list of tester names to load default hooks from (eg: ['py', 'haskell']) 
        cwd: all hooks will be run as if cwd is this directory (or actual current directory if None)
        args: args to pass to each hook
        kwargs: kwargs to pass to each hook
        """
        self.custom_hooks_path = custom_hooks_path
        self.testers = [] if testers is None else testers
        self.cwd = cwd
        self.args = [] if args is None else args
        self.kwargs = {} if kwargs is None else kwargs
        self.load_errors = []
        self.run_errors = []
        self.hooks = self._load_all()
        self._context = deque()

    @staticmethod
    def _select_builtins(tester_info, _info=None):
        """
        Return a nested dictionary containing the hooks to apply based
        based on tester_info. Hook functions are included in the output
        dictionary only if their name is a key in tester_info and the 
        value for that key is truthy.

        The keys in the output dictionaries are determined by the value 
        of the 'context' key in builtin_hooks.HOOKS and any dependencies 
        specified in builtin_hooks.HOOKS are loaded as well.

        >>> tester_info = {'upload_feedback_file': True}
        >>> Hooks._select_builtins(tester_info)
        {'each': {'after': [<function hooks_context.builtin_hooks.upload_feedback_file ... >]}} 

        >>> tester_info = {'upload_feedback_file': False}
        >>> Hooks._select_builtins(tester_info)
        {}

        >>> tester_info = {'upload_feedback_to_repo': True} # has clear_feedback_file as a dependency
        >>> Hooks._select_builtins(tester_info)
        {'each': {'after': [<function hooks_context.builtin_hooks.upload_feedback_to_repo ... >],
                  'before': [<function hooks_context.builtin_hooks.clear_feedback_file ... >]}}
        """
        if _info is None:
            _info = defaultdict(lambda: defaultdict(list))

        for func_name, data in builtin_hooks.HOOKS.items():
            if tester_info.get(func_name):
                hook_type, hook_context = data['context'].split('_')
                func = getattr(builtin_hooks, func_name)
                if func not in _info.get(hook_context, {}).get(hook_type, set()):
                    _info[hook_context][hook_type].append(func)
                    for requires in data.get('requires', []):
                        Hooks._select_builtins({requires: True}, _info)
        return _info

    @staticmethod
    def _merge_hook_dicts(*hook_dicts):
        """
        Return a dictionary created by merging all dictionaries in hook_dicts. 
        hook_dicts are merged by concatenating all value lists together. These 
        lists are then sorted according to whether their names are in HOOK_BASENAMES
        and then alphabetically. This ensures that hooks are always executed in the same
        order. 
        """
        merged = defaultdict(list)
        for d in hook_dicts:
            for key, hooks in d.items():
                merged[key].extend(h for h in hooks if h)
        for key, hooks in merged.items():
            merged[key] = sorted((h for h in hooks if h),
                                 key=lambda x: (x.__name__ in Hooks.HOOK_BASENAMES, x.__name__),
                                 reverse=(key == 'after'))
        return merged

    def _load_all(self):
        """
        Return a dictionary containing all hooks that may be run over the course of a test run. 
        This dictionary contains three nested levels: The key at the first level indicates the 
        name of the tester ('py', 'haskell', etc.) or None if the hook is one of HOOK_BASENAMES. 
        The key at the second level indicates the context in which the hook should be run ('all' 
        or 'each'). The key at the third level indicates when the hook should be run ('before' or
        'after'). The values at the third level contain a list of hooks. 

        Hook functions are loaded from builtin_hooks.HOOKS, builtin_hooks.DEFAULT_HOOKS (which are
        loaded from the default_hooks.py files for each tester) and the custom_hooks_path file (if 
        specified).
        """
        hooks = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        custom_hooks_module = self._load_module(self.custom_hooks_path)
        
        for hook_name in Hooks.HOOK_BASENAMES:
            hook_type, hook_context = hook_name.split('_')  # eg. "before_all" -> ("before", "all")
            custom_hook = self._load_hook(custom_hooks_module, hook_name)
            builtin_hook = builtin_hooks.DEFAULT_HOOKS.get(hook_name)
            hooks[None][hook_context][hook_type].extend([custom_hook, builtin_hook])
            for tester_type in self.testers:
                tester_hook_name = f'{hook_name}_{tester_type}'
                custom_hook = self._load_hook(custom_hooks_module, tester_hook_name)
                builtin_hook = builtin_hooks.DEFAULT_HOOKS.get(tester_hook_name)
                hooks[tester_type][hook_context][hook_type].extend([custom_hook, builtin_hook])
        return hooks

    def _load_module(self, hooks_script_path):
        """
        Return module loaded from hook_script_path. Log any error
        messages that were raised when trying to import the module
        to self.load_errors.
        """
        hooks_script_path = os.path.realpath(hooks_script_path)
        if os.path.isfile(hooks_script_path):
            dirpath = os.path.dirname(hooks_script_path)
            basename = os.path.basename(hooks_script_path)
            module_name, _ = os.path.splitext(basename)
            try:
                with add_path(dirpath):
                    hooks_module = __import__(module_name)
                return hooks_module
            except Exception as e:
                self.load_errors.append((module_name, f'{traceback.format_exc()}\n{e}'))
        return None

    def _load_hook(self, module, function_name):
        """
        Return function named function_name from module or None if the function
        doesn't exist in that module's namespace or if the function is not a
        Callable object.
        """
        try:
            func = getattr(module, function_name)
            if isinstance(func, Callable):
                return func
            else:
                self.load_errors.append((module.__name__, f'hook function {function_name} is not callable'))
        except AttributeError:
            return

    def _run(self, func, extra_args=None, extra_kwargs=None):
        """
        Run the function func with positional and keyword arguments obtained by 
        merging self.args with extra_args and self.kwargs with extra_kwargs.
        """
        args = self.args+(extra_args or [])
        kwargs = {**self.kwargs, **(extra_kwargs or {})}
        try:
            func(*args, **kwargs)
        except BaseException as e:
            self.run_errors.append((func.__name__, args, kwargs, f'{traceback.format_exc()}\n{e}'))

    def _get_hooks(self, tester_type, builtin_selector=None):
        """
        Return list of hooks to run before and after a given block of code according
        to the tester_type and the builtin_selector dictionary. tester_type should be 
        either 'all', 'each', or the name of a tester ('pyta', 'sql', etc.) and the 
        builtin_selector is passed to Hooks._select_builtins to select which builtin hooks
        should be used. Also return the result of Hooks._select_builtins or an empty dict
        if no builtin hooks are used.  
        """
        builtin_hook_dict = Hooks._select_builtins(builtin_selector or {})
        if tester_type == 'all':
            hooks = self.hooks.get(None, {}).get('all', {})
        elif tester_type == 'each':
            hooks = self.hooks.get(None, {}).get('each', {})
            other_hooks = [builtin_hook_dict.get('each', {})]
            for context in self._context:
                context_hooks = self.hooks.get(context, {}).get('each', {})
                other_hooks.append(context_hooks)
            hooks = Hooks._merge_hook_dicts(hooks, *other_hooks)
        else:
            hooks = self.hooks.get(tester_type, {}).get('all', {})
            hooks = Hooks._merge_hook_dicts(hooks, builtin_hook_dict.get('all', {}))
        return hooks.get('before', []), hooks.get('after', [])

    @contextmanager
    def around(self, tester_type, builtin_selector=None, extra_args=None, extra_kwargs=None, cwd=None):
        """
        Context manager used to run hooks around any block of code. Hooks are selected based on the tester type (one
        of 'all', 'each', or the name of a tester), a builtin_selector (usually the test settings for a given test
        group). If extra_args or extra_kwargs are specified, these will be passed to each hook in addition to self.args
        and self.kwargs. If cwd is specified, each hook will be run as if the current working directory were cwd.
        """
        before, after = self._get_hooks(tester_type, builtin_selector)
        if tester_type not in {'all', 'each'}:
            self._context.append(tester_type)
        try:
            if any(before) or any(after):
                try:
                    with current_directory(cwd or self.cwd):
                        for hook in before:
                            self._run(hook, extra_args, extra_kwargs)
                    yield
                finally:
                    with current_directory(cwd or self.cwd):
                        for hook in after:
                            self._run(hook, extra_args, extra_kwargs)
            else:
                yield
        finally:
            if tester_type not in {'all', 'each'}:
                self._context.pop()

    def format_errors(self):
        """
        Return a string containing the data from self.load_errors and self.run_errors.
        """
        error_list = []
        for module_name, tb in self.load_errors:
            error_list.append(f'module_name: {module_name}\ntraceback:\n{tb}')
        for hook_name, args, kwargs, tb in self.run_errors:   
            error_list.append(f'function_name: {hook_name}\n'
                              f'args: {self.args}\nkwargs: {self.kwargs},\ntraceback:\n{tb}')
        return '\n\n'.join(error_list)
