# Thanks to this blog post for how to load env vars with the yaml loader:
#   https://medium.com/swlh/python-yaml-configuration-with-environment-variables-parsing-77930f4273ac

import os
import re
from collections.abc import Mapping
import yaml
from autotester import CONFIG_ROOT

DEFAULT_ROOT = os.path.join(os.path.dirname(__file__), 'defaults')

class _Config:

    _local_config = os.path.join(CONFIG_ROOT, 'config_local.yml')
    _default_config = os.path.join(DEFAULT_ROOT, 'config_default.yml')
    _env_var_config = os.path.join(DEFAULT_ROOT, 'config_env_vars.yml')
    _env_pattern = re.compile(r'.*?\${(\w+)}.*?')
    _env_tag = '!ENV'
    _env_not_found_key = '!ENVIRONMENT VARIABLE NOT FOUND!'

    def __init__(self):
        self._yaml_loader = yaml.SafeLoader
        self._yaml_loader.add_implicit_resolver(self._env_tag, self._env_pattern, None)
        self._yaml_loader.add_constructor(self._env_tag, self._env_var_constructor)
        self._settings = self._load_from_yaml()

    def __getitem__(self, key):
        try:
            return self._settings[key]
        except KeyError:
            if isinstance(key, tuple):
                d = self
                for k in key:
                    d = d[k]
                return d
            raise

    @classmethod
    def _merge_dicts(cls, dicts):
        try:
            _merged = dicts[0].copy()
        except AttributeError:
            _merged = dicts[0]
        if all(isinstance(d, Mapping) for d in dicts):
            for d in dicts[1:]:
                for key, val in d.items():
                    if key not in _merged or _merged[key] == cls._env_not_found_key:
                        _merged[key] = val
                    else:
                        _merged[key] = cls._merge_dicts([_merged[key], val])
        return _merged

    def _env_var_constructor(self, loader, node):
        value = loader.construct_scalar(node)
        match = self._env_pattern.findall(value)
        if match:
            full_value = value
            for g in match:
                full_value = full_value.replace(f'${{{g}}}', os.environ.get(g, self._env_not_found_key))
            return full_value
        return value

    def _load_from_yaml(self):
        config_dicts = []
        if os.path.isfile(self._local_config):
            with open(self._local_config) as f:
                local_config = yaml.load(f, Loader=self._yaml_loader)
                if local_config is not None:
                    config_dicts.append(local_config)
        with open(self._env_var_config) as f:
            config_dicts.append(yaml.load(f, Loader=self._yaml_loader))
        with open(self._default_config) as f:
            config_dicts.append(yaml.load(f, Loader=self._yaml_loader))
        return self._merge_dicts(config_dicts)

config = _Config()
