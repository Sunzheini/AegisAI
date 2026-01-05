"""
Interface indicating that a class requires a Cloud Manager.
"""

import abc
from typing import Any


class INeedCloudManagerInterface(abc.ABC):
    """
    Interface indicating that a class requires a Redis Manager.
    """

    @property
    def cloud_manager(self) -> Any:
        """
        Property to get the CloudManager instance.
        Subclasses may override if they need custom behavior.
        """
        return getattr(self, "_cloud_manager", None)

    @cloud_manager.setter
    def cloud_manager(self, value: Any) -> None:
        """
        Property setter to set the CloudManager instance.
        """
        setattr(self, "_cloud_manager", value)
