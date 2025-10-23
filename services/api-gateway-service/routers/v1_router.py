"""
This module defines the API router for version 1 (v1) of the API.
"""
import os

from fastapi import APIRouter

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.needs.ResolveNeedsManager import ResolveNeedsManager
else:
    from needs.ResolveNeedsManager import ResolveNeedsManager
# ------------------------------------------------------------------------------------------

from views.ingestion_views import IngestionViewsManager
from routers.auth_router import get_current_user


router = APIRouter(
    prefix="/v1",
    tags=["v1"],
)

# Register the versioned ingestion endpoints on this router
views_manager = IngestionViewsManager(router, get_current_user)
ResolveNeedsManager.resolve_needs(views_manager)
