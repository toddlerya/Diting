from typing import Dict, List
from simulator.projections.base import BaseProjection
from simulator.event_bus import EventBus

class MetricProjection(BaseProjection):
    def __init__(self, bus: EventBus):
        super().__init__(bus)
        # session_id -> metric_name -> list of points
        self.metrics_db: Dict[str, Dict[str, List[dict]]] = {}
    
    def record_metric(self, session_id: str, metric_name: str, tick: int, value: float):
        if session_id not in self.metrics_db:
            self.metrics_db[session_id] = {}
        if metric_name not in self.metrics_db[session_id]:
            self.metrics_db[session_id][metric_name] = []
        self.metrics_db[session_id][metric_name].append({"tick": tick, "value": value})
        
    def query_metric(self, session_id: str, metric_name: str, start_tick: int, end_tick: int) -> List[dict]:
        session_metrics = self.metrics_db.get(session_id, {})
        points = session_metrics.get(metric_name, [])
        return [pt for pt in points if start_tick <= pt["tick"] <= end_tick]
