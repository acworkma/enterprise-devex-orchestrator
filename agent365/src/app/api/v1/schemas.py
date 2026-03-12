"""API v1 request/response schemas.

Keep Pydantic models here so routers stay thin.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    """Schema for creating a new item."""

    name: str = Field(..., min_length=1, max_length=120, description="Item name")
    description: str = Field(default="", max_length=500, description="Item description")


class ItemResponse(BaseModel):
    """Schema returned by item endpoints."""

    id: str = Field(..., description="Unique item identifier")
    name: str = Field(..., description="Item name")
    description: str = Field(default="", description="Item description")
    project: str = Field(..., description="Owning project name")
