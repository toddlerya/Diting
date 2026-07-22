from pathlib import Path
from typing import Any

import yaml

from simulator.clock import SimulationClock
from simulator.entity import Entity
from simulator.event_bus import BaseEvent, EventBus, EventSeverity, EventType
from simulator.schema import RetryPolicyConfig


class Scenario:
    def __init__(self, name: str, description: str, steps: list[dict[str, Any]], seed: int = 42):
        self.name = name
        self.description = description
        self.steps = steps
        self.seed = seed

    @classmethod
    def from_yaml(cls, filepath: str) -> "Scenario":
        """
        从 YAML 文件加载故障剧本，并解析 nested include 关系
        """
        path = Path(filepath).resolve()
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        steps = []
        includes = data.get("include", [])

        # simulator 根目录为当前文件所在目录
        simulator_dir = Path(__file__).resolve().parent

        for inc in includes:
            inc_p = Path(inc)
            # 兼容 include 写法：可以是绝对路径，也可以是 "scenarios/xxx.yaml" 或相对于当前 YAML 的路径
            if inc_p.is_absolute():
                inc_path = inc_p
            else:
                # 尝试相对于 simulator 目录
                inc_path = simulator_dir / inc_p
                if not inc_path.exists():
                    # 尝试相对于当前 yaml 所在的目录
                    inc_path = path.parent / inc_p

            if inc_path.exists():
                inc_scenario = cls.from_yaml(str(inc_path))
                steps.extend(inc_scenario.steps)
            else:
                raise FileNotFoundError(f"Included scenario file not found: {inc}")

        # 将当前 yaml 的 steps 追加进去
        steps.extend(data.get("steps", []))

        # 按 tick 升序排列
        steps.sort(key=lambda x: x.get("tick", 0))

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            steps=steps,
            seed=data.get("seed", 42),
        )

    def apply(
        self,
        tick: int,
        entities: dict[str, Entity],
        bus: EventBus,
        clock: SimulationClock,
        session_id: str = "default",
    ):
        """
        在特定的 Tick 下执行当前剧本声明的所有故障注入和状态变更
        """

        def replace_session_id(val: Any) -> Any:
            if isinstance(val, dict):
                return {k: replace_session_id(v) for k, v in val.items()}
            elif isinstance(val, list):
                return [replace_session_id(v) for v in val]
            elif isinstance(val, str):
                return val.replace("{session_id}", session_id)
            return val

        for step in self.steps:
            if step.get("tick") != tick:
                continue

            # 1. 物理资源/属性变更
            if "target" in step and "value" in step:
                target = step["target"]
                value = step["value"]

                parts = target.split(".")
                if len(parts) >= 2:
                    entity_id = parts[0]
                    entity = entities.get(entity_id)
                    if entity:
                        # 如 redis.resources.used -> parts: ['redis', 'resources', 'used']
                        if parts[1] == "resources" and len(parts) == 3:
                            resource_key = parts[2]
                            if resource_key == "retry_policy" and isinstance(value, dict):
                                setattr(
                                    entity.resources,
                                    resource_key,
                                    RetryPolicyConfig.model_validate(value),
                                )
                            else:
                                setattr(entity.resources, resource_key, value)
                        else:
                            # 允许其他属性修改 (如 target = gateway.some_prop)
                            setattr(entity, parts[1], value)

            # 2. 发布物理事件 (如 Firing Alerts, Critical Logs)
            if "event" in step:
                evt_cfg = step["event"]
                entity_id = evt_cfg.get("entity_id", "")
                severity = evt_cfg.get("severity", EventSeverity.INFO)
                event_type = evt_cfg.get("event_type", EventType.GENERIC)
                payload = replace_session_id(evt_cfg.get("payload", {}))
                trace_id = evt_cfg.get("trace_id")

                # 生成确定性的 event_id
                event_id = f"evt_s_{tick}_{entity_id}_{event_type}_{hash(str(payload)) % 10000}"

                bus.publish(
                    BaseEvent(
                        event_id=event_id,
                        tick=tick,
                        timestamp=clock.now(),
                        entity_id=entity_id,
                        severity=severity,
                        event_type=event_type,
                        payload=payload,
                        trace_id=trace_id,
                    )
                )
