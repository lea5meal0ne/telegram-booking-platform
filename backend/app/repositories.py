"""Shared persistence helpers; domain rules live in services.py."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import Base


async def get_or_404(db: AsyncSession, model: type[Base], identifier: int):
    entity = await db.get(model, identifier)
    if entity is None:
        raise HTTPException(404, "not_found")
    return entity
