# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.core.cache import cache

if TYPE_CHECKING:
    from uuid import UUID


logger = logging.getLogger(__name__)

DEBUG_CACHING = False


@dataclass
class UserProjectPermissionInfo:
    user: int | None
    teams: list[int]


class UserProjectPermissionCache:
    def __init__(self) -> None:
        raise RuntimeError("This class should never be instanciated")

    @classmethod
    def cache_key(cls, user_id: int, project_id: UUID) -> str:
        return f"[{cls.__name__}]user:{user_id}=>project:{project_id}"

    @classmethod
    def get(cls, user_id: int, project_id: UUID) -> UserProjectPermissionInfo | None:
        return None
        cache_key = cls.cache_key(user_id, project_id)

        if (rslt := cache.get(cache_key)) is None:
            if DEBUG_CACHING:
                logger.info(f"{cls.__name__} CACHE MISS [{cache_key}] !")
            return None

        if DEBUG_CACHING:
            logger.info(f"{cls.__name__} CACHE HIT [{cache_key}] !")
        return UserProjectPermissionInfo(**rslt)

    @classmethod
    def set(
        cls,
        user_id: int,
        project_id: UUID,
        payload: UserProjectPermissionInfo,
        timeout: int = 300,
    ) -> None:
        cache_key = cls.cache_key(user_id, project_id)
        cache.set(cache_key, payload.__dict__, timeout=timeout)

        if DEBUG_CACHING:
            logger.info(f"{cls.__name__} CACHE SET [{cache_key}] !")

    @classmethod
    def delete(cls, user_id: int, project_id: UUID) -> None:
        cache_key = cls.cache_key(user_id, project_id)
        cache.delete(cache_key)

        if DEBUG_CACHING:
            logger.info(f"{cls.__name__} CACHE CLEAR [{cache_key}] !")
