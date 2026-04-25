"""Rate limiting middleware template for LAB 05."""

from typing import Callable

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.infrastructure.redis_client import get_redis
from app.infrastructure.cache_keys import payment_rate_limit_key


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-based rate limiting для endpoint оплаты.

    Цель:
    - защита от DDoS/шторма запросов;
    - защита от случайных повторных кликов пользователя.
    """

    def __init__(self, app, limit_per_window: int = 5, window_seconds: int = 10):
        super().__init__(app)
        self.limit_per_window = limit_per_window
        self.window_seconds = window_seconds
        self._redis = get_redis()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        TODO: Реализовать Redis rate limiting.

        Рекомендуемая логика:
        1) Применять только к endpoint оплаты:
           - /api/orders/{order_id}/pay
           - /api/payments/retry-demo
        2) Сформировать subject:
           - user_id (если есть), иначе client IP.
        3) Использовать Redis INCR + EXPIRE:
           - key = rate_limit:pay:{subject}
           - если counter > limit_per_window -> 429 Too Many Requests.
        4) Для прохождения запроса добавить в ответ headers:
           - X-RateLimit-Limit
           - X-RateLimit-Remaining
        """

        # Заглушка: ограничение пока не применяется.
        # TODO: заменить на полноценную реализацию.
        path = request.url.path

        is_payment_endpoint = (
            path.startswith("/api/orders/") and path.endswith("/pay")
        ) or (
            path == "/api/payments/retry-demo"
        )
        if not is_payment_endpoint:
            return await call_next(request)

        subject = self._get_subject(request)
        key = payment_rate_limit_key(subject)

        current = await self._redis.incr(key)

        if current == 1:
            await self._redis.expire(key, self.window_seconds)

        remaining = max(0, self.limit_per_window - current)

        if current > self.limit_per_window:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests"},
                headers={
                    "X-RateLimit-Limit": str(self.limit_per_window),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(self.window_seconds),
                },
            )

        response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(self.limit_per_window)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

    def _get_subject(self, request: Request) -> str:
        user_id = request.headers.get("x-user-id")
        if user_id:
            return user_id

        client_ip = request.client.host if request.client else "unknown"
        return client_ip
