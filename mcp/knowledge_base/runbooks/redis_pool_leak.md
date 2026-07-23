# Redis Connection Pool Leak Runbook

## Description
PaymentService or OrderService fails to acquire Redis connection due to pool connection leak or unclosed active connections.

## Symptoms
- Log: `Failed to acquire Redis connection (50/50 active)`
- Metric: `redis_active_connections` hits maximum limit (100%).
- Trace: Downstream calls to Redis report `TIMEOUT` error status.

## Resolution
1. Restart PaymentService to release leaked connection handles.
2. Scale up `max_connections` in Redis pool configuration.
