# Service Out Of Memory (OOM) Runbook

## Description
Microservice crashes or responds with high latency due to JVM heap memory exhaustion.

## Symptoms
- Log: `java.lang.OutOfMemoryError: Java heap space`
- Metric: `heap_used_mb` reaches `max_heap_mb`.
- Metric: CPU usage spikes to 100% due to frequent Full GC cycles.

## Resolution
1. Collect heap dump for memory leak analysis.
2. Increase service `max_heap_mb` memory limit in environment configuration.
3. Restart microservice instance.
