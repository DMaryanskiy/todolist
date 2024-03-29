from fastapi import APIRouter

from tasks.services import task_router
from todolists.services import todolist_router
from users.services import user_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(user_router, prefix="/users")
api_router.include_router(todolist_router, prefix="/lists")
api_router.include_router(task_router, prefix="/tasks")
