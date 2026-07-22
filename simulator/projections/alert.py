from datetime import datetime

from simulator.clock import SimulationClock
from simulator.event_bus import BaseEvent, EventBus
from simulator.projections.base import BaseProjection


class AlertmanagerProjection(BaseProjection):
    """
    Alertmanager 告警生命周期投影层。
    订阅并处理 Metric 越线 (`MetricThresholdExceeded`) 与指标自愈/恢复 (`MetricThresholdRecovered`) 事件。
    负责维护活动的 Firing Alerts 告警状态机，以及在告警消解时追加 endsAt 并将其移入 Resolved 列表。
    """

    def __init__(self, bus: EventBus, clock: SimulationClock):
        super().__init__(bus, clock)
        # 会话活跃告警字典：session_id -> alertname -> active alert dict
        self.firing_alerts: dict[str, dict[str, dict]] = {}
        # 会话消解告警列表：session_id -> list of resolved alert dicts
        self.resolved_alerts: dict[str, list[dict]] = {}

        self.bus.subscribe("MetricThresholdExceeded", self._handle_exceeded)
        self.bus.subscribe("MetricThresholdRecovered", self._handle_recovered)

    def _handle_exceeded(self, event: BaseEvent):
        """
        处理指标越线事件，当该告警在当前 session 中不存在时将其置为 firing 状态。
        """
        payload = event.payload
        session_id = payload.get("session_id", "default")
        alertname = payload.get("alertname", "Unknown")

        if session_id not in self.firing_alerts:
            self.firing_alerts[session_id] = {}

        if alertname not in self.firing_alerts[session_id]:
            self.firing_alerts[session_id][alertname] = {
                "status": "firing",
                "labels": {
                    "alertname": alertname,
                    "service": payload.get("service", "unknown"),
                    "severity": event.severity,
                },
                "annotations": {"summary": payload.get("summary", "")},
                "starts_tick": event.tick,
                "ends_tick": None,
            }

    def _handle_recovered(self, event: BaseEvent):
        """
        处理指标自愈恢复事件，将对应的告警从 Firing 剔除并记录 ends_tick。
        """
        payload = event.payload
        session_id = payload.get("session_id", "default")
        alertname = payload.get("alertname", "Unknown")

        if session_id in self.firing_alerts and alertname in self.firing_alerts[session_id]:
            alert = self.firing_alerts[session_id].pop(alertname)
            alert["status"] = "resolved"
            alert["ends_tick"] = event.tick

            if session_id not in self.resolved_alerts:
                self.resolved_alerts[session_id] = []
            self.resolved_alerts[session_id].append(alert)

    def get_firing_alerts(self, session_id: str, real_now: datetime) -> list[dict]:
        """获取当前 session 激活中的报警队列，并映射至现实时间。"""
        alerts = list(self.firing_alerts.get(session_id, {}).values())
        results = []
        for a in alerts:
            # 动态拷贝并计算 startsAt
            starts_at = self.aligner.align_timestamp(a["starts_tick"], real_now)
            item = dict(a)
            item["startsAt"] = starts_at.isoformat()
            item["endsAt"] = None
            # 隐藏内部 tick 实现
            item.pop("starts_tick", None)
            item.pop("ends_tick", None)
            results.append(item)
        return results

    def get_resolved_alerts(self, session_id: str, real_now: datetime) -> list[dict]:
        """获取当前 session 已消解恢复的历史报警列表，并映射至现实时间。"""
        alerts = self.resolved_alerts.get(session_id, [])
        results = []
        for a in alerts:
            starts_at = self.aligner.align_timestamp(a["starts_tick"], real_now)
            ends_at = (
                self.aligner.align_timestamp(a["ends_tick"], real_now) if a["ends_tick"] else None
            )
            item = dict(a)
            item["startsAt"] = starts_at.isoformat()
            item["endsAt"] = ends_at.isoformat() if ends_at else None
            item.pop("starts_tick", None)
            item.pop("ends_tick", None)
            results.append(item)
        return results
