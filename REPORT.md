# Отчёт по лабораторной работе №5
## Redis-кэш, консистентность и rate limiting

**Студент:** Артём
**Группа:** 
**Дата:** 2026-04-18

## 1. Реализация Redis-кэша

Реализован кэш для двух сущностей:

| Сущность | Ключ | TTL |
|----------|------|-----|
| Каталог товаров | `catalog:v1` | 300 сек |
| Карточка заказа | `order_card:v1:{order_id}` | 120 сек |

**Логика cache hit/miss:**
- При запросе `use_cache=true` сначала проверяется Redis
- При cache hit — данные возвращаются из Redis
- При cache miss — данные читаются из БД PostgreSQL, затем сохраняются в Redis с TTL

**Реализация:** `backend/app/application/cache_service.py`

## 2. Демонстрация неконсистентности (намеренно сломанный сценарий)

**Шаги:**
1. Прогрев кэша: GET `/api/cache-demo/orders/{order_id}/card?use_cache=true`
2. Изменение заказа в БД: POST `/api/cache-demo/orders/{order_id}/mutate-without-invalidation`
3. Повторный запрос: GET `/api/cache-demo/orders/{order_id}/card?use_cache=true`

**Результат:** Клиент получает stale данные (старый `total_amount`) вместо актуальных из БД. Это демонстрирует проблему отсутствия инвалидации.

**Реализация:** `backend/app/api/cache_demo_routes.py` - endpoint `mutate-without-invalidation`

## 3. Починка через событийную инвалидацию

**Механизм:**
1. При изменении заказа вызывается `CacheInvalidationEventBus.publish_order_updated()`
2. Обработчик события удаляет связанные ключи из Redis

**Инвалидируемые ключи:**
- `order_card:v1:{order_id}` — кэш карточки изменённого заказа
- `catalog:v1` — кэш каталога (т.к. изменение может влиять на агрегаты)

**Реализация:** `backend/app/application/cache_events.py`

## 4. Rate limiting endpoint оплаты через Redis

**Параметры:**
- Лимит: **5 запросов** за окно **10 секунд**
- Ключ: `rate_limit:pay:{subject}` (subject = user_id или client IP)
- При превышении: **429 Too Many Requests**

**Заголовки ответа:**
- `X-RateLimit-Limit: 5`
- `X-RateLimit-Remaining: N` (оставшиеся запросы)

**Реализация:** `backend/app/middleware/rate_limit_middleware.py`

## 5. Бенчмарки RPS до/после кэша

| Endpoint | use_cache | RPS | Avg Latency |
|----------|-----------|-----|-------------|
| `/api/cache-demo/orders/{id}/card` | false | 691 | 131ms |
| `/api/cache-demo/orders/{id}/card` | true | 841 | 131ms |
| `/api/cache-demo/catalog` | false | 673 | 238ms |
| `/api/cache-demo/catalog` | true | 906 | 123ms |

## 6. Выводы

1. **Кэш эффективен для тяжёлых запросов** — каталог показал -49% latency и +35% RPS. Для order_card выигрыш меньше (+22% RPS) из-за простого запроса — накладные расходы на Redis сопоставимы с самим запросом.

2. **Инвалидация сложнее кэширования** — пропуск инвалидации приводит к stale data. Тесты подтвердили: после изменения заказа без инвалидации кэш возвращает старый total_amount.

3. **Rate limiting полезен даже при бизнес-валидациях** — защищает от повторных кликов на оплату, уменьшает нагрузку на БД до обработки бизнес-логики.

4. **Событийная инвалидация — правильный паттерн** — decouple изменения данных от очистки кэша. CacheInvalidationEventBus.publish_order_updated() вызывается после commit, гарантирует consistency.

5. **TTL нужно балансировать** — catalog: 300с, order_card: 120с. Для каталога больший TTL оправдан (данные меняются редко), для заказов — меньший (быстрее консистентность).