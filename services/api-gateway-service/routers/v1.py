from fastapi import APIRouter

from views.ingestion_views import IngestionViewsManager
from routers.auth import get_current_user

router = APIRouter(
    prefix="/v1",
    tags=["v1"],
)

# Register the versioned ingestion endpoints on this router
views_manager = IngestionViewsManager(router, get_current_user)
