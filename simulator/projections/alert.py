from typing import Dict, List
from simulator.event_bus import EventBus, BaseEvent

class AlertmanagerProjection:
    def __init__(self, bus: EventBus):
        self.bus = bus
        # session_id -> alertname -> active alert dict
        self.firing_alerts: Dict[str, Dict[str, dict]] = {}
        # session_id -> list of resolved alert dicts
        self.resolved_alerts: Dict[str, List[dict]] = {}
        
        self.bus.subscribe("MetricThresholdExceeded", self._handle_exceeded)
        self.bus.subscribe("MetricThresholdRecovered", self._handle_recovered)
        
    def _handle_exceeded(self, event: BaseEvent):
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
        return list(self.firing_alerts.get(session_id, {}).values())
          
    def get_resolved_alerts(self, session_id: str) -> List[dict]:
        return self.resolved_alerts.get(session_id, [])
