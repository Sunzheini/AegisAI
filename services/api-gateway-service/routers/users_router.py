"""
Router for user-related endpoints.
"""

from fastapi import APIRouter

from db_management.db_manager import DataBaseManager
from needs.ResolveNeedsManager import ResolveNeedsManager
from views.users_views import UsersViewsManager
from routers.auth_router import get_current_user


router = APIRouter(
    prefix="/users",
    tags=["users"],
)

db_manager = DataBaseManager()
views_manager = UsersViewsManager(router, get_current_user)
ResolveNeedsManager.resolve_needs(views_manager)
