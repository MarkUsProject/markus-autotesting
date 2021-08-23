# Thanks to this blog post for how to load env vars with the yaml loader:
#   https://medium.com/swlh/python-yaml-configuration-with-environment-variables-parsing-77930f4273ac

import os
import re
import json
from typing import Pattern, Tuple, Union, TypeVar, ClassVar, List, Dict, Callable, Optional, Any
from collections.abc import Mapping
import jsonschema
import yaml

DEFAULT_ROOT = os.path.dirname(__file__)
ConfigValues = TypeVar("ConfigValues", List, Dict, str, int, float, type(None))


class _Config:

    _replacement_pattern: ClassVar[Pattern] = re.compile(r".*?\${(\w+)}.*?")
    _not_found_key: ClassVar[str] = ""

    def __init__(self) -> None:
        """
        Initialize a configuration object that stores the configuration settings
        after loading them from one or several configuration file.

        Loading configuration files may also require resolving values by parsing
        environment variables.
        """
        self._yaml_loader = yaml.SafeLoader

        self._yaml_loader.add_implicit_resolver("!ENV", self._replacement_pattern, None)
        env_constructor = self._constructor_factory(lambda g: os.environ.get(g, self._not_found_key))
        self._yaml_loader.add_constructor("!ENV", env_constructor)

        self._settings = self._load_from_yaml()
        self._validate()

    def __getitem__(self, key: Union[str, Tuple[Union[str, int], ...]]) -> ConfigValues:
        """
        Return the value in self._settings that corresponds to key.

        If key is a tuple, then this method will chain __getitem__ calls.
        For example:

            config['a', 'b', 'c'] is equivalent to config['a']['b']['c']
        """
        try:
            return self._settings[key]
        except KeyError:
            if isinstance(key, tuple):
                d = self
                for k in key:
                    d = d[k]
                return d
            raise

    def get(
        self, key: Union[str, Tuple[Union[str, int], ...]], default: Optional[Any] = None
    ) -> Optional[ConfigValues]:
        """
        Call self.__getitem__ with key. Return default if the key cannot
        be found
        """
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def to_json(self) -> str:
        """
        Return a json representation of self._settings
        """
        return json.dumps(self._settings)

    @classmethod
    def _merge_dicts(cls, dicts: List[Dict[str, ConfigValues]]) -> Dict[str, ConfigValues]:
        """
        Returns a merged dictionary created from merging all dictionaries in dicts
        in order.
        """
        try:
            _merged = dicts[0].copy()
        except AttributeError:
            _merged = dicts[0]
        if all(isinstance(d, Mapping) for d in dicts):
            for d in dicts[1:]:
                for key, val in d.items():
                    if key not in _merged or _merged[key] == cls._not_found_key:
                        _merged[key] = val
                    else:
                        _merged[key] = cls._merge_dicts([_merged[key], val])
        return _merged

    def _constructor_factory(self, replacement_func: Callable) -> Callable:
        """
        Returns a constructor function used to load data from a yaml file.

        Meant for use when calling yaml.add_constructor to add a new constructor
        for a given yaml tag.
        """

        def constructor(loader, node, pattern=self._replacement_pattern):
            """
            Replaces the value of a yaml node with the return value of replacement_func
            if the current value matches _replacement_pattern.

            Used in this case to replace values with the !ENV tag with the environment
            variable that follows the !ENV tag in curly braces. For example, if there is
            currently an environment variable WORKSPACE with value '/workspace':

                replaces: !{ENV} ${WORKSPACE}
                with: '/workspace'
            """
            value = loader.construct_scalar(node)
            match = pattern.findall(value)
            if match:
                full_value = value
                for g in match:
                    full_value = full_value.replace(f"${{{g}}}", replacement_func(g))
                return full_value
            return value

        return constructor

    def _validate(self):
        with open(os.path.join(DEFAULT_ROOT, "settings_schema.json")) as f:
            schema = json.load(f)
        jsonschema.Draft7Validator(schema).validate(self._settings)

    def _load_from_yaml(self) -> Dict[str, ConfigValues]:
        """
        Returns a dictionary containing all data loaded from the various yaml
        configuration files (default and user specified).
        """
        config_dicts = []
        base_settings = os.path.join(DEFAULT_ROOT, "settings.yml")
        local_settings = os.path.join(DEFAULT_ROOT, "settings.local.yml")
        env_settings = os.environ.get("AUTOTESTER_CONFIG")
        for settings_file in (env_settings, local_settings, base_settings):
            if settings_file and os.path.isfile(settings_file):
                with open(settings_file) as f:
                    local_config = yaml.load(f, Loader=self._yaml_loader)
                    if local_config is not None:
                        config_dicts.append(local_config)
        return self._merge_dicts(config_dicts)


config = _Config()
