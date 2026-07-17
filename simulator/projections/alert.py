from typing import Dict, List
from simulator.projections.base import BaseProjection
from simulator.event_bus import EventBus, BaseEvent

class AlertmanagerProjection(BaseProjection):
    """
    Alertmanager 告警生命周期投影层。
    订阅并处理 Metric 越线 (`MetricThresholdExceeded`) 与指标自愈/恢复 (`MetricThresholdRecovered`) 事件。
    负责维护活动的 Firing Alerts 告警状态机，以及在告警消解时追加 endsAt 并将其移入 Resolved 列表。
    """
    def __init__(self, bus: EventBus):
        super().__init__(bus)
        # 会话活跃告警字典：session_id -> alertname -> active alert dict
        self.firing_alerts: Dict[str, Dict[str, dict]] = {}
        # 会话消解告警列表：session_id -> list of resolved alert dicts
        self.resolved_alerts: Dict[str, List[dict]] = {}
        
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
                    "severity": event.severity
                },
                "annotations": {
                    "summary": payload.get("summary", "")
                },
                "startsAt": event.timestamp.isoformat(),
                "endsAt": None
            }
              
    def _handle_recovered(self, event: BaseEvent):
        """
        处理指标自愈恢复事件，将对应的告警从 Firing 剔除并打上 endsAt 写入 Resolved 历史。
        """
        payload = event.payload
        session_id = payload.get("session_id", "default")
        alertname = payload.get("alertname", "Unknown")
        
        if session_id in self.firing_alerts and alertname in self.firing_alerts[session_id]:
            alert = self.firing_alerts[session_id].pop(alertname)
            alert["status"] = "resolved"
            alert["endsAt"] = event.timestamp.isoformat()
            
            if session_id not in self.resolved_alerts:
                self.resolved_alerts[session_id] = []
            self.resolved_alerts[session_id].append(alert)
              
    def get_firing_alerts(self, session_id: str) -> List[dict]:
        """获取当前 session 激活中的报警队列。"""
        return list(self.firing_alerts.get(session_id, {}).values())
          
    def get_resolved_alerts(self, session_id: str) -> List[dict]:
        """获取当前 session 已消解恢复的历史报警列表。"""
        return self.resolved_alerts.get(session_id, [])

