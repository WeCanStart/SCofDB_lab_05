-- wrk script: GET order card endpoint
-- Usage:
-- wrk -t4 -c100 -d30s -s loadtest/wrk/order_card.lua http://localhost:8082
--
-- TODO: перед запуском подставьте валидный order_id в path.

wrk.method = "GET"
wrk.path = "/api/cache-demo/orders/{{3931dee6-e8a9-434e-842f-abb72f515088}}/card?use_cache=true"
