import json
from collections.abc import Mapping
from typing import Any, Union, Tuple, Iterable, Optional


class MarkusTestSpecs(Mapping):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """ Initialize a MarkUsTestSpecs instance """
        self._specs = dict(*args, **kwargs)

    @classmethod
    def from_json(cls, json_str: str) -> "MarkusTestSpecs":
        """ Return a MarkUsTestSpecs instance created from a json string """
        return cls(json.loads(json_str))

    def __getitem__(self, key: Union[str, Tuple]) -> Any:
        """
        Behaves like a regular dict.__getitem__ except
        if the key is not found and the key is a tuple
        it will descend into any potential nested dictionaries
        using each element in the tuple as a key in the next
        nested dictionary

        >>> my_dict = MarkusTestSpecs({'a':{'b':{'c': 123}}})
        >>> my_dict['a','b','c']
        123
        >>> my_dict['a','b']
        {'c': 123}
        """
        try:
            return self._specs[key]
        except KeyError:
            if isinstance(key, tuple):
                d = self
                for k in key:
                    d = d[k]
                return d
            raise

    def __iter__(self) -> Iterable:
        """ Return an iterator over self._specs """
        return iter(self._specs)

    def __len__(self) -> int:
        """ Return the length of self._specs """
        return len(self._specs)

    def get(self, *keys: str, default: Optional[Any] = None) -> Any:
        """
        Behaves like a regular dict.get except if there
        are multiple keys it will use __getitem__ to
        descend into any potential nested dictionaries.

        >>> my_dict = {'a':{'b':{'c':123}}}
        >>> my_dict.get('a','b','c')
        123
        >>> my_dict.get('a','b','d')
        >>> my_dict.get('a','b','d', default=1)
        1
        >>> my_dict.get('b', 2, '5.', default=2)
        2
        """
        try:
            return super().get(keys, default=default)
        except TypeError:
            return default
