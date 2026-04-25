"""
LAB 05: Проверка починки через событийную инвалидацию.
"""

import pytest
import time
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_order_card_is_fresh_after_event_invalidation():
    """
    TODO: Реализовать сценарий:
    1) Прогреть кэш карточки заказа.
    2) Изменить заказ через mutate-with-event-invalidation.
    3) Убедиться, что ключ карточки инвалидирован.
    4) Повторный GET возвращает свежие данные из БД, а не stale cache.
    """
    unique_ts = int(time.time() * 1000)
    test_email = f"cache_event_{unique_ts}@test.com"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        user_response = await client.post(
            "/api/users",
            json={"email": test_email, "name": "Cache Event Test"}
        )
        assert user_response.status_code in (200, 201), f"User creation failed: {user_response.status_code}"
        user_id = user_response.json()["id"]

        order_response = await client.post(
            "/api/orders",
            json={"user_id": user_id}
        )
        order_id = order_response.json()["id"]

        add_item_response = await client.post(
            f"/api/orders/{order_id}/items",
            json={
                "product_name": "Event Test Product",
                "price": 100.00,
                "quantity": 2
            }
        )

        initial_card = await client.get(
            f"/api/cache-demo/orders/{order_id}/card?use_cache=true"
        )
        assert initial_card.status_code == 200
        initial_data = initial_card.json()
        initial_total = initial_data["total_amount"]

        new_total = initial_total + 999.0

        mutate_response = await client.post(
            f"/api/cache-demo/orders/{order_id}/mutate-with-event-invalidation",
            json={"new_total_amount": new_total}
        )
        assert mutate_response.status_code == 200

        fresh_card = await client.get(
            f"/api/cache-demo/orders/{order_id}/card?use_cache=true"
        )
        assert fresh_card.status_code == 200
        fresh_data = fresh_card.json()

        assert fresh_data["total_amount"] == new_total, (
            f"Expected fresh data with new total {new_total}, "
            f"got {fresh_data['total_amount']}"
        )
