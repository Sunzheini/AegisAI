"""
Contains the manager to resolve needs for needy objects.
"""
# try:
#     from .INeedRedisManager import INeedRedisManagerInterface
#     from ..redis_management.redis_manager import RedisManager
# except:
#     from needs.INeedRedisManager import INeedRedisManagerInterface
#     from redis_management.redis_manager import RedisManager

from needs.INeedRedisManager import INeedRedisManagerInterface
from redis_management.redis_manager import RedisManager


class ResolveNeedsManager:
    """
    Manager to resolve needs for needy objects.
    """

    @staticmethod
    def resolve_needs(needy_instance: object):
        """
        Resolve needs for the given needy object (instance of a class).
        Only works with instances, not classes.
        """
        if isinstance(needy_instance, type):
            raise ValueError(
                "resolve_needs() only works with instances, not classes. "
                f"Received class: {needy_instance.__name__}"
            )

        # Check if the instance's class implements the Redis interface
        if INeedRedisManagerInterface in needy_instance.__class__.__mro__:
            needy_instance.redis_manager = RedisManager()
