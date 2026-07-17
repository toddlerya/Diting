from datetime import datetime, timezone, timedelta
import pytest
from simulator.clock import SimulationClock, TimeAligner
from simulator.event_bus import EventBus, BaseEvent

def test_simulation_clock_alignment():
    start = datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc)
    # 步长 100ms
    clock = SimulationClock(start, timedelta(milliseconds=100))
    assert clock.current_tick == 0
    assert clock.now() == start

    clock.tick() # tick = 1
    clock.tick() # tick = 2
    assert clock.current_tick == 2
    
    # 动态 Now 映射对齐校验
    real_now = datetime(2026, 7, 17, 14, 0, 0, tzinfo=timezone.utc)
    aligner = TimeAligner(clock)
    # 最后一个 tick (tick = 2) 应该被精确映射为 real_now
    assert aligner.align_timestamp(2, real_now) == real_now
    # 第 1 个 tick 应该被偏移回 100ms 之前
    assert aligner.align_timestamp(1, real_now) == real_now - timedelta(milliseconds=100)

def test_event_bus():
    bus = EventBus()
    received = []
    
    def handler(event):
        received.append(event)
        
    bus.subscribe("test_event", handler)
    
    event = BaseEvent(
        event_id="evt_1",
        tick=0,
        timestamp=datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc),
        entity_id="service_a",
        severity="INFO",
        event_type="test_event",
        payload={"data": 123}
    )
    
    bus.publish(event)
    assert len(received) == 1
    assert received[0].payload["data"] == 123
    assert received[0].trace_id is None
