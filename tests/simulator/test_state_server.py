from datetime import UTC, datetime

from fastapi.testclient import TestClient

from simulator.clock import SimulationClock
from simulator.event_bus import BaseEvent, EventBus
from simulator.projections.alert import AlertmanagerProjection
from simulator.projections.log import LogProjection
from simulator.projections.metric import MetricProjection
from simulator.projections.trace import TraceProjection
from simulator.state_server import create_app


def test_state_server_endpoints():
    bus = EventBus()
    clock = SimulationClock(datetime(2026, 7, 17, 9, 0, 0, tzinfo=UTC))

    metric_proj = MetricProjection(bus, clock)
    log_proj = LogProjection(bus, clock)
    trace_proj = TraceProjection(bus, clock)
    alert_proj = AlertmanagerProjection(bus, clock)

    # 注入测试数据
    metric_proj.record_metric("sess_web", "cpu_usage", 5, 45.2)

    bus.publish(
        BaseEvent(
            event_id="e_web_1",
            tick=3,
            timestamp=clock.now(),
            entity_id="OrderService",
            severity="CRITICAL",
            event_type="ResourceExhausted",
            payload={"session_id": "sess_web", "msg": "DB fail"},
            trace_id="tr_web",
        )
    )

    bus.publish(
        BaseEvent(
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
                "service": "Gateway",
            },
        )
    )

    app = create_app(metric_proj, log_proj, trace_proj, alert_proj)
    client = TestClient(app)

    real_now_str = "2026-07-17T14:00:00+00:00"

    # 1. 测 Metric API
    resp = client.get(
        f"/api/v1/metrics?session_id=sess_web&metric=cpu_usage&start_tick=0&end_tick=10&real_now={real_now_str}"
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["value"] == 45.2
    assert "timestamp" in resp.json()[0]

    # 2. 测 Log API (过滤 level=CRITICAL 时能拿到，过滤 WARNING 时为噪点测试)
    resp = client.get(
        f"/api/v1/logs?session_id=sess_web&service=OrderService&level=CRITICAL&real_now={real_now_str}"
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert "DB fail" in resp.json()[0]
    assert "2026-07-17T14:00:00" in resp.json()[0]

    # 3. 测 Alert API
    resp = client.get(f"/api/v1/alerts?session_id=sess_web&status=firing&real_now={real_now_str}")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["labels"]["alertname"] == "GatewayHighLatency"
    assert resp.json()[0]["startsAt"] is not None

    # 4. 测 DELETE API
    del_resp = client.delete("/api/v1/session?session_id=sess_web")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "cleared"

    # 验证清空后查不到
    assert len(metric_proj.query_metric("sess_web", "cpu_usage", 0, 10, datetime.now(UTC))) == 0
    assert len(alert_proj.get_firing_alerts("sess_web", datetime.now(UTC))) == 0
