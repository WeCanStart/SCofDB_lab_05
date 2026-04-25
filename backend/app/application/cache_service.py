"""Cache service template for LAB 05."""

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.redis_client import get_redis
from app.infrastructure.cache_keys import catalog_key, order_card_key


CATALOG_TTL_SECONDS = 300
ORDER_CARD_TTL_SECONDS = 120


class CacheService:
    """
    Сервис кэширования каталога и карточки заказа.

    TODO:
    - реализовать методы через Redis client + БД;
    - добавить TTL и версионирование ключей.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._redis: Optional[Any] = None

    @property
    def redis(self):
        if self._redis is None:
            self._redis = get_redis()
        return self._redis

    async def get_catalog(self, *, use_cache: bool = True) -> list[dict[str, Any]]:
        if use_cache:
            cached = await self.redis.get(catalog_key())
            if cached:
                return json.loads(cached)

        query = text("""
            SELECT
                oi.product_name,
                count(*) AS order_lines,
                sum(oi.quantity) AS sold_qty,
                round(avg(oi.price)::numeric, 2) AS avg_price
            FROM order_items oi
            GROUP BY oi.product_name
            ORDER BY sold_qty DESC
            LIMIT 100
        """)
        result = await self.db.execute(query)
        rows = result.fetchall()
        catalog = [
            {
                "product_name": row.product_name,
                "order_lines": row.order_lines,
                "sold_qty": row.sold_qty,
                "avg_price": float(row.avg_price) if row.avg_price else 0.0,
            }
            for row in rows
        ]

        if use_cache:
            await self.redis.setex(
                catalog_key(),
                CATALOG_TTL_SECONDS,
                json.dumps(catalog),
            )

        return catalog

    async def get_order_card(self, order_id: str, *, use_cache: bool = True) -> dict[str, Any]:
        cache_key = order_card_key(order_id)

        if use_cache:
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

        query = text("""
            SELECT
                o.id AS order_id,
                o.user_id,
                o.status,
                o.total_amount,
                o.created_at,
                array_agg(
                    json_build_object(
                        'id', oi.id,
                        'product_name', oi.product_name,
                        'price', oi.price,
                        'quantity', oi.quantity
                    )
                ) AS items
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            WHERE o.id = :order_id
            GROUP BY o.id
        """)
        result = await self.db.execute(query, {"order_id": order_id})
        row = result.fetchone()

        if not row:
            raise ValueError(f"Order {order_id} not found")

        order_card = {
            "order_id": str(row.order_id),
            "user_id": str(row.user_id),
            "status": row.status,
            "total_amount": float(row.total_amount) if row.total_amount else 0.0,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "items": row.items or [],
        }

        if use_cache:
            await self.redis.setex(
                cache_key,
                ORDER_CARD_TTL_SECONDS,
                json.dumps(order_card),
            )

        return order_card

    async def invalidate_order_card(self, order_id: str) -> None:
        """Удалить ключ карточки заказа из Redis."""
        await self.redis.delete(order_card_key(order_id))

    async def invalidate_catalog(self) -> None:
        """Удалить ключ каталога из Redis."""
        await self.redis.delete(catalog_key())
