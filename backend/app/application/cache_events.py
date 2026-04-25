"""Event-driven cache invalidation template for LAB 05."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from app.infrastructure.cache_keys import catalog_key, order_card_key
from app.infrastructure.redis_client import get_redis


@dataclass
class OrderUpdatedEvent:
    """Событие изменения заказа."""

    order_id: str


class CacheInvalidationEventBus:
    """
    Минимальный event bus для LAB 05.

    TODO:
    - реализовать publish/subscribe;
    - на OrderUpdatedEvent инвалидировать:
      - order_card:v1:{order_id}
      - catalog:v1 (если изменение затрагивает агрегаты каталога).
    """

    def __init__(self):
        self._redis = get_redis()
        self._subscribers: Dict[str, List[Callable]] = {
            "order_updated": [],
        }

    async def publish_order_updated(self, event: OrderUpdatedEvent) -> None:
        await self._invalidate_order_card(event.order_id)
        await self._invalidate_catalog()

    async def _invalidate_order_card(self, order_id: str) -> None:
        key = order_card_key(order_id)
        await self._redis.delete(key)

    async def _invalidate_catalog(self) -> None:
        key = catalog_key()
        await self._redis.delete(key)
