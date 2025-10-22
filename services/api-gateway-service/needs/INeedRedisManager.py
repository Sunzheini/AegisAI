"""
Interface indicating that a class requires a Redis Manager.
"""

import abc
from typing import Any


class INeedRedisManagerInterface(abc.ABC):
    """
    Interface indicating that a class requires a Redis Manager.
    """

    @property
    def redis_manager(self) -> Any:
        """
        Property to get the Redis Manager instance.
        Default implementation returns the stored `_redis_manager` attribute or None.
        Subclasses may override if they need custom behavior.
        """
        return getattr(self, "_redis_manager", None)

    @redis_manager.setter
    def redis_manager(self, value: Any) -> None:
        """
        Property setter to set the Redis Manager instance.
        Stores the provided value on the instance as `_redis_manager`.
        """
        setattr(self, "_redis_manager", value)
