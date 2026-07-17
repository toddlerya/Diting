import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from simulator.event_bus import EventBus, BaseEvent
from simulator.clock import SimulationClock
from simulator.projections.metric import MetricProjection
from simulator.projections.log import LogProjection
from simulator.projections.trace import TraceProjection
from simulator.projections.alert import AlertmanagerProjection
from simulator.state_server import create_app

def test_state_server_endpoints():
    bus = EventBus()
    clock = SimulationClock(datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc))
    
    metric_proj = MetricProjection(bus)
    log_proj = LogProjection(bus)
    trace_proj = TraceProjection(bus, clock)
    alert_proj = AlertmanagerProjection(bus)
    
    # 注入测试数据
    metric_proj.record_metric("sess_web", "cpu_usage", 5, 45.2)
    
    bus.publish(BaseEvent(
        event_id="e_web_1",
        tick=3,
        timestamp=clock.now(),
        entity_id="OrderService",
        severity="CRITICAL",
        event_type="ResourceExhausted",
        payload={"session_id": "sess_web", "msg": "DB fail"},
        trace_id="tr_web"
    ))
    
    bus.publish(BaseEvent(
        event_id="e_web_2",
        tick=2,
        timestamp=clock.now(),
        entity_id="Gateway",
        severity="WARNING",
        event_type="MetricThresholdExceeded",
        payload={
            "session_id": "sess_web",
            "alertname": "GatewayHighLatency",
            "summary": "Gateway response slow",
            "service": "Gateway"
        }
    ))
    
    app = create_app(metric_proj, log_proj, trace_proj, alert_proj)
    client = TestClient(app)
    
    # 1. 测 Metric API
    resp = client.get("/api/v1/metrics?session_id=sess_web&metric=cpu_usage&start_tick=0&end_tick=10")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["value"] == 45.2
    
    # 2. 测 Log API
    resp = client.get("/api/v1/logs?session_id=sess_web&service=OrderService&level=CRITICAL")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert "DB fail" in resp.json()[0]
    
    # 3. 测 Alert API
    resp = client.get("/api/v1/alerts?session_id=sess_web&status=firing")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["labels"]["alertname"] == "GatewayHighLatency"
    
    # 4. 测 DELETE API (零 I/O 内存清空)
    del_resp = client.delete("/api/v1/session?session_id=sess_web")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "cleared"
    
    # 验证清空后查不到
    assert len(metric_proj.query_metric("sess_web", "cpu_usage", 0, 10)) == 0
    assert len(alert_proj.get_firing_alerts("sess_web")) == 0
