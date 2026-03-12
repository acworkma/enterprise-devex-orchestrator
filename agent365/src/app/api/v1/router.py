"""API v1 router -- versioned business endpoints.

Mount this router in main.py under /api/v1.
Add domain-specific routes here as the application grows.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from api.v1.schemas import ItemCreate, ItemResponse
from core.dependencies import get_settings, get_repository
from core.config import Settings
from core.services import ItemService
from azure.storage.blob import BlobServiceClient
from core.dependencies import get_blob_service

router = APIRouter()


@router.get("/items", response_model=list[ItemResponse], summary="List items")
async def list_items(settings: Settings = Depends(get_settings)):
    """Return items from the service layer."""
    repo = get_repository("item", settings.storage_mode)
    svc = ItemService(project_name=settings.app_name, repo=repo)
    return svc.list_items()


@router.post("/items", response_model=ItemResponse, status_code=201, summary="Create item")
async def create_item(payload: ItemCreate, settings: Settings = Depends(get_settings)):
    """Create a new item via the service layer."""
    repo = get_repository("item", settings.storage_mode)
    svc = ItemService(project_name=settings.app_name, repo=repo)
    return svc.create_item(payload.name, payload.description)


@router.get("/items/{item_id}", summary="Get item by ID")
async def get_item(item_id: str, settings: Settings = Depends(get_settings)):
    repo = get_repository("item", settings.storage_mode)
    svc = ItemService(project_name=settings.app_name, repo=repo)
    item = svc.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.put("/items/{item_id}", summary="Update item")
async def update_item(item_id: str, payload: ItemCreate, settings: Settings = Depends(get_settings)):
    repo = get_repository("item", settings.storage_mode)
    svc = ItemService(project_name=settings.app_name, repo=repo)
    item = svc.update_item(item_id, payload.name, payload.description)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/items/{item_id}", status_code=204, summary="Delete item")
async def delete_item(item_id: str, settings: Settings = Depends(get_settings)):
    repo = get_repository("item", settings.storage_mode)
    svc = ItemService(project_name=settings.app_name, repo=repo)
    if not svc.delete_item(item_id):
        raise HTTPException(status_code=404, detail="Item not found")


@router.get("/storage/containers", summary="List storage containers")
async def list_containers(
    storage: BlobServiceClient = Depends(get_blob_service),
):
    containers = [c["name"] for c in storage.list_containers(max_results=10)]
    return {"containers": containers}
