from datetime import datetime
from typing import Dict, List
from simulator.projections.base import BaseProjection
from simulator.clock import SimulationClock, TimeAligner
from simulator.event_bus import EventBus, BaseEvent

class TraceProjection(BaseProjection):
    def __init__(self, bus: EventBus, clock: SimulationClock):
        super().__init__(bus)
        self.clock = clock
        self.aligner = TimeAligner(clock)
        # session_id -> list of traces
        self.traces_db: Dict[str, List[dict]] = {}
        self.bus.subscribe("TraceFinishedEvent", self._handle_event)
        
    def _handle_event(self, event: BaseEvent):
        payload = event.payload
        session_id = payload.get("session_id", "default")
        request = payload.get("request")
        if request:
            if session_id not in self.traces_db:
                self.traces_db[session_id] = []
            self.traces_db[session_id].append({
                "tick": event.tick,
                "request": request
            })
            
    def query_traces(self, session_id: str, real_now: datetime) -> List[dict]:
        session_traces = self.traces_db.get(session_id, [])
        results = []
        for item in session_traces:
            aligned_time = self.aligner.align_timestamp(item["tick"], real_now)
            results.append({
                "trace_id": item["request"].trace_id,
                "timestamp": aligned_time.isoformat(), # 转换为 ISO 字符串
                "request": item["request"]
            })
        return results
