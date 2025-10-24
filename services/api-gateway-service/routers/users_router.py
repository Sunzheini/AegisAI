"""
Router for user-related endpoints.
"""
import os

from dotenv import load_dotenv
from fastapi import APIRouter

from db_management.db_manager import DataBaseManager

load_dotenv()

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.needs.ResolveNeedsManager import ResolveNeedsManager
else:
    from needs.ResolveNeedsManager import ResolveNeedsManager
# ------------------------------------------------------------------------------------------

from views.users_views import UsersViewsManager
from routers.auth_router import get_current_user


router = APIRouter(
    prefix="/users",
    tags=["users"],
)

db_manager = DataBaseManager()
views_manager = UsersViewsManager(router, get_current_user)
ResolveNeedsManager.resolve_needs(views_manager)
