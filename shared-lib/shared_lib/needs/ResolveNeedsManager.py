"""
Contains the manager to resolve needs for needy objects.
"""
# try:
#     from .INeedRedisManager import INeedRedisManagerInterface
#     from ..redis_management.redis_manager import RedisManager
# except:
#     from needs.INeedRedisManager import INeedRedisManagerInterface
#     from redis_management.redis_manager import RedisManager

from shared_lib.needs.INeedRedisManager import INeedRedisManagerInterface
from shared_lib.redis_management.redis_manager import RedisManager


# class ResolveNeedsManager:
#     """
#     Manager to resolve needs for needy objects.
#     """

#     @staticmethod
#     def resolve_needs(needy_instance: object):
#         """
#         Resolve needs for the given needy object (instance of a class).
#         Only works with instances, not classes.
#         """
#         if isinstance(needy_instance, type):
#             raise ValueError(
#                 "resolve_needs() only works with instances, not classes. "
#                 f"Received class: {needy_instance.__name__}"
#             )

#         # Check if the instance's class implements the Redis interface
#         if INeedRedisManagerInterface in needy_instance.__class__.__mro__:
#             needy_instance.redis_manager = RedisManager()

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
        print(f"[DEBUG ResolveNeedsManager] Resolving needs for: {type(needy_instance).__name__}")
        
        if isinstance(needy_instance, type):
            raise ValueError(
                "resolve_needs() only works with instances, not classes. "
                f"Received class: {needy_instance.__name__}"
            )

        # Check if the instance's class implements the Redis interface
        if INeedRedisManagerInterface in needy_instance.__class__.__mro__:
            print(f"[DEBUG ResolveNeedsManager] Instance implements interface, setting redis_manager")
            needy_instance.redis_manager = RedisManager()
            print(f"[DEBUG ResolveNeedsManager] redis_manager set to: {needy_instance.redis_manager}")
        else:
            print(f"[DEBUG ResolveNeedsManager] Instance does NOT implement interface")
            print(f"[DEBUG ResolveNeedsManager] MRO: {needy_instance.__class__.__mro__}")
