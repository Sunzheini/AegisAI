from fastapi import APIRouter

from models.temp_db import DataBaseManager
from views.views import ViewsManager
from routers.auth import get_current_user


router = APIRouter(
    prefix='/users',
    tags=['users'],
)

db_manager = DataBaseManager()
views_manager = ViewsManager(router, get_current_user)
