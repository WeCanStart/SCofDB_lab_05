"""
LAB 05: Rate limiting endpoint оплаты через Redis.
"""

import pytest
import time
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_payment_endpoint_rate_limit():
    """
    TODO: Реализовать тест.

    Рекомендуемая проверка:
    1) Сделать N запросов оплаты в пределах одного окна.
    2) Проверить, что первые <= limit проходят.
    3) Следующие запросы получают 429 Too Many Requests.
    4) Проверить заголовки X-RateLimit-Limit / X-RateLimit-Remaining.
    """
    unique_ts = int(time.time() * 1000)
    test_email = f"rate_limit_{unique_ts}@test.com"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        user_response = await client.post(
            "/api/users",
            json={"email": test_email, "name": "Rate Limit Test"}
        )
        assert user_response.status_code in (200, 201), f"User creation failed"
        user_id = user_response.json()["id"]

        order_response = await client.post(
            "/api/orders",
            json={"user_id": user_id}
        )
        order_id = order_response.json()["id"]

        limit = 5
        passed = 0
        rejected = 0
        limit_headers = []

        for i in range(10):
            response = await client.post(
                f"/api/orders/{order_id}/pay"
            )

            if response.status_code == 429:
                rejected += 1
            else:
                passed += 1
                if "X-RateLimit-Limit" in response.headers:
                    limit_headers.append({
                        "limit": response.headers.get("X-RateLimit-Limit"),
                        "remaining": response.headers.get("X-RateLimit-Remaining"),
                    })

        assert passed <= limit, f"Expected max {limit} requests to pass, got {passed}"
        assert rejected >= 5, f"Expected at least 5 requests to be rejected, got {rejected}"

        if limit_headers:
            assert limit_headers[0]["limit"] == "5"
            assert int(limit_headers[0]["remaining"]) < 5
