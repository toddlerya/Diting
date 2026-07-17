import os
import pytest
from datetime import datetime, timezone
from simulator.scenario import Scenario
from simulator.entity import InfraEntity
from simulator.event_bus import EventBus
from simulator.clock import SimulationClock

def test_scenario_load_and_include(tmp_path):
    # 模拟被包含的子剧本 (included.yaml)
    inc_content = """
name: base_scenario
description: base description
steps:
  - tick: 1
    target: "redis.resources.used"
    value: 10
  - tick: 2
    event:
      entity_id: "db"
      severity: "WARNING"
      event_type: "SlowQuery"
      payload:
        msg: "Query took 200ms"
"""
    # 模拟主剧本 (main_scenario.yaml)
    main_content = """
name: main_scenario
description: main description
include:
  - included.yaml
steps:
  - tick: 2
    target: "redis.resources.used"
    value: 20
  - tick: 3
    event:
      entity_id: "gateway"
      severity: "CRITICAL"
      event_type: "OOM"
      payload:
        session_id: "{session_id}"
"""
    
    inc_file = tmp_path / "included.yaml"
    inc_file.write_text(inc_content)
    
    main_file = tmp_path / "main_scenario.yaml"
    main_file.write_text(main_content)
    
    # 加载剧本
    scenario = Scenario.from_yaml(str(main_file))
    
    assert scenario.name == "main_scenario"
    # 总共 4 个 steps (2 来自 included, 2 来自 main)
    assert len(scenario.steps) == 4
    
    # 验证是否按照 tick 排好序了
    ticks = [step["tick"] for step in scenario.steps]
    assert ticks == [1, 2, 2, 3]

def test_scenario_apply():
    clock = SimulationClock(datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc))
    bus = EventBus()
    
    redis = InfraEntity("redis", "RedisPool")
    redis.resources["used"] = 0
    redis.resources["capacity"] = 50
    entities = {"redis": redis}
    
    steps = [
        {
            "tick": 1,
            "target": "redis.resources.used",
            "value": 30
        },
        {
            "tick": 2,
            "event": {
                "entity_id": "redis",
                "severity": "CRITICAL",
                "event_type": "ConnectionTimeout",
                "payload": {
                    "session_id": "{session_id}",
                    "detail": "Failed to connect"
                }
            }
        }
    ]
    
    scenario = Scenario("test", "test desc", steps)
    
    events = []
    # 订阅事件总线以记录事件
    bus.subscribe("ConnectionTimeout", lambda e: events.append(e))
    
    # 应用第 1 tick
    scenario.apply(1, entities, bus, clock, session_id="session_abc")
    assert redis.resources["used"] == 30
    assert len(events) == 0
    
    # 应用第 2 tick
    scenario.apply(2, entities, bus, clock, session_id="session_abc")
    assert len(events) == 1
    assert events[0].payload["session_id"] == "session_abc"
    assert events[0].payload["detail"] == "Failed to connect"
    assert events[0].entity_id == "redis"
    assert events[0].severity == "CRITICAL"
