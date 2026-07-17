from datetime import datetime, timezone, timedelta
import pytest
from simulator.event_bus import EventBus, BaseEvent
from simulator.pipeline import SpanNode, Request
from simulator.projections.metric import MetricProjection
from simulator.projections.log import LogProjection
from simulator.projections.trace import TraceProjection
from simulator.projections.alert import AlertmanagerProjection

def test_alertmanager_lifecycle_in_projection():
    bus = EventBus()
    alert_proj = AlertmanagerProjection(bus)
    
    # 模拟以 session_id = "sess_1" 投递告警事件
    now = datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc)
    
    # 1. 触发越线 firing 告警
    bus.publish(BaseEvent(
        event_id="e1",
        tick=10,
        timestamp=now,
        entity_id="Gateway",
        severity="CRITICAL",
        event_type="MetricThresholdExceeded",
        payload={
            "session_id": "sess_1",
            "alertname": "ServiceHighErrorRate",
            "summary": "Gateway error rate is 12%",
            "service": "Gateway"
        }
    ))
    
    firing = alert_proj.get_firing_alerts("sess_1")
    assert len(firing) == 1
    assert firing[0]["status"] == "firing"
    assert firing[0]["endsAt"] is None
    
    # 2. 触发消解 resolved 告警
    bus.publish(BaseEvent(
        event_id="e2",
        tick=30,
        timestamp=now + timedelta(seconds=2),
        entity_id="Gateway",
        severity="INFO",
        event_type="MetricThresholdRecovered",
        payload={
            "session_id": "sess_1",
            "alertname": "ServiceHighErrorRate",
            "service": "Gateway"
        }
    ))
    
    firing_after = alert_proj.get_firing_alerts("sess_1")
    resolved_after = alert_proj.get_resolved_alerts("sess_1")
    
    assert len(firing_after) == 0
    assert len(resolved_after) == 1
    assert resolved_after[0]["status"] == "resolved"
    assert resolved_after[0]["endsAt"] is not None

def test_log_projection_noise():
    bus = EventBus()
    # 使用固定种子 seed = 42 实例化，使其偶发日志生成 100% 稳定可测试
    log_proj = LogProjection(bus, seed=42)
    
    # 正常事件投递，以 session_id="sess_log" 注入
    bus.publish(BaseEvent(
        event_id="e3",
        tick=5,
        timestamp=datetime.now(timezone.utc),
        entity_id="PaymentService",
        severity="CRITICAL",
        event_type="ResourceExhausted",
        payload={"session_id": "sess_log", "msg": "Redis pool full"},
        trace_id="tr_123"
    ))
    
    # 对应 CRITICAL 级别查询
    logs = log_proj.query_logs("sess_log", "PaymentService", "CRITICAL")
    assert len(logs) >= 1
    assert "tr_123" in logs[0]
    
    # 验证是否产生了偶发警告噪声日志
    warn_logs = log_proj.query_logs("sess_log", "PaymentService", "WARNING")
    assert len(warn_logs) >= 1
    assert "Transient connection jitter" in warn_logs[0]

def test_trace_projection_alignment():
    bus = EventBus()
    # 传入时钟与对齐器的 Mock/真实状态
    # 假设 tick = 10，步长 100ms
    from simulator.clock import SimulationClock
    clock = SimulationClock(datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc))
    clock.current_tick = 10
    
    trace_proj = TraceProjection(bus, clock)
    
    # 组装物理树
    root = SpanNode("sp_root", None, "gateway")
    request = Request("trace_align_1", root)
    
    # 投递 Trace 结束事件
    bus.publish(BaseEvent(
        event_id="e4",
        tick=10,
        timestamp=clock.now(),
        entity_id="gateway",
        severity="INFO",
        event_type="TraceFinishedEvent",
        payload={"session_id": "sess_trace", "request": request}
    ))
    
    real_now = datetime(2026, 7, 17, 14, 0, 0, tzinfo=timezone.utc)
    traces = trace_proj.query_traces("sess_trace", real_now)
    assert len(traces) == 1
    
    # 最后一个 tick (10) 的时间戳必须映射对齐为 real_now 字符串
    assert traces[0]["timestamp"] == real_now.isoformat()
