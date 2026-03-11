"""API v1 router -- versioned business endpoints.

Mount this router in main.py under /api/v1.
Add domain-specific routes here as the application grows.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from api.v1.schemas import ItemCreate, ItemResponse
from core.dependencies import get_settings
from core.config import Settings
from core.services import ItemService

router = APIRouter()


@router.get("/items", response_model=list[ItemResponse], summary="List items")
async def list_items(
    settings: Settings = Depends(get_settings),
):
    """Return items from the service layer."""
    svc = ItemService(project_name=settings.app_name)
    return svc.list_items()


@router.post("/items", response_model=ItemResponse, status_code=201, summary="Create item")
async def create_item(
    payload: ItemCreate,
    settings: Settings = Depends(get_settings),
):
    """Create a new item via the service layer."""
    svc = ItemService(project_name=settings.app_name)
    return svc.create_item(payload.name, payload.description)
