import random
from datetime import datetime
from typing import Dict, List
from simulator.projections.base import BaseProjection
from simulator.event_bus import EventBus, BaseEvent

class LogProjection(BaseProjection):
    def __init__(self, bus: EventBus, seed: int = 42):
        super().__init__(bus)
        self.random_gen = random.Random(seed)
        # session_id -> list of logs
        self.logs_db: Dict[str, List[dict]] = {}
        self.bus.subscribe("ResourceExhausted", self._handle_event)
        
    def _handle_event(self, event: BaseEvent):
        payload = event.payload
        session_id = payload.get("session_id", "default")
        if session_id not in self.logs_db:
            self.logs_db[session_id] = []
            
        log_line = f"[{event.timestamp.isoformat()}] [{event.severity}] [trace_id: {event.trace_id}] {event.entity_id}: Failed due to {payload.get('msg', 'Unknown Error')}"
        self.logs_db[session_id].append({
            "tick": event.tick,
            "service": event.entity_id,
            "level": event.severity,
            "message": log_line
        })
        
    def query_logs(self, session_id: str, service: str, level: str) -> List[str]:
        session_logs = self.logs_db.get(session_id, [])
        results = []
        for log in session_logs:
            if log["service"] == service and log["level"] == level:
                results.append(log["message"])
                
        # 仅当查询条件是 WARNING 级别时，才混入 WARNING 噪点日志以防污染其他级别
        if level == "WARNING" and self.random_gen.random() < 0.8:
            noise_line = f"[{datetime.now().isoformat()}] [WARNING] [trace_id: None] {service}: Transient connection jitter (noise)"
            if session_id not in self.logs_db:
                self.logs_db[session_id] = []
            results.append(noise_line)
            
        return results
