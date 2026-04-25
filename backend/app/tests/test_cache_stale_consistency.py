"""
LAB 05: Демонстрация неконсистентности кэша.
"""

import pytest
import uuid
import time
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_stale_order_card_when_db_updated_without_invalidation():
    """
    TODO: Реализовать сценарий:
    1) Прогреть кэш карточки заказа (GET /api/cache-demo/orders/{id}/card?use_cache=true).
    2) Изменить заказ в БД через endpoint mutate-without-invalidation.
    3) Повторно запросить карточку с use_cache=true.
    4) Проверить, что клиент получает stale данные из кэша.
    """
    unique_ts = int(time.time() * 1000)
    test_email = f"cache_stale_{unique_ts}@test.com"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        user_response = await client.post(
            "/api/users",
            json={"email": test_email, "name": "Cache Stale Test"}
        )
        if user_response.status_code not in (200, 201):
            print(f"User creation failed: {user_response.status_code}, {user_response.text}")
        assert user_response.status_code in (200, 201), f"User creation failed: {user_response.status_code} {user_response.text}"
        user_data = user_response.json()
        print(f"User response: {user_data}")
        user_id = user_data["id"]

        order_response = await client.post(
            "/api/orders",
            json={"user_id": user_id}
        )
        order_id = order_response.json()["id"]

        add_item_response = await client.post(
            f"/api/orders/{order_id}/items",
            json={
                "product_name": "Test Product",
                "price": 100.00,
                "quantity": 2
            }
        )

        initial_card = await client.get(
            f"/api/cache-demo/orders/{order_id}/card?use_cache=true"
        )
        if initial_card.status_code != 200:
            print(f"Initial card failed: {initial_card.status_code}, {initial_card.text}")
        assert initial_card.status_code == 200
        initial_data = initial_card.json()
        initial_total = initial_data["total_amount"]

        new_total = initial_total + 500.0

        mutate_response = await client.post(
            f"/api/cache-demo/orders/{order_id}/mutate-without-invalidation",
            json={"new_total_amount": new_total}
        )
        assert mutate_response.status_code == 200

        cached_card = await client.get(
            f"/api/cache-demo/orders/{order_id}/card?use_cache=true"
        )
        assert cached_card.status_code == 200
        cached_data = cached_card.json()

        assert cached_data["total_amount"] == initial_total, (
            "Expected stale data from cache (old total_amount), "
            f"got {cached_data['total_amount']}, expected {initial_total}"
        )
        assert cached_data["total_amount"] != new_total, (
            "Should get stale cache, not fresh data"
        )
