from datetime import datetime
from typing import Optional, Callable, Dict, List

class BaseEvent:
    def __init__(self, event_id: str, tick: int, timestamp: datetime, 
                 entity_id: str, severity: str, event_type: str, 
                 payload: dict, trace_id: Optional[str] = None):
        self.event_id = event_id
        self.tick = tick
        self.timestamp = timestamp
        self.entity_id = entity_id
        self.severity = severity
        self.event_type = event_type
        self.payload = payload
        self.trace_id = trace_id

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        
    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        
    def publish(self, event: BaseEvent):
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            handler(event)
