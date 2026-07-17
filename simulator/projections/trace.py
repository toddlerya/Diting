from datetime import datetime
from typing import Dict, List
from simulator.projections.base import BaseProjection
from simulator.clock import SimulationClock, TimeAligner
from simulator.event_bus import EventBus, BaseEvent

class TraceProjection(BaseProjection):
    """
    链路投影层 (OTel/Jaeger Mock)。
    监听来自事件总线中完成请求的 TraceFinishedEvent，将其物理树结构缓存，
    并在查询时调用 TimeAligner 将其对齐转换至现实物理 Now 时间。
    """
    def __init__(self, bus: EventBus, clock: SimulationClock):
        super().__init__(bus, clock)
        # 内存 Trace 数据库：session_id -> list of traces
        self.traces_db: Dict[str, List[dict]] = {}
        # 订阅已完成的请求 Trace 事件
        self.bus.subscribe("TraceFinishedEvent", self._handle_event)
        
    def _handle_event(self, event: BaseEvent):
        """
        处理请求结束事件，将完整的 Span 树骨架及性能数据载入缓存。
        """
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
        """
        查询分布式链路追踪结果，并将其时间轴对齐为发起评测的实时物理时间。
        
        Args:
            session_id (str): 诊断会话 ID。
            real_now (datetime): 当前评测发起物理 Now 时刻。
            
        Returns:
            List[dict]: 带有对齐时间戳的 Trace 字典列表。
        """
        session_traces = self.traces_db.get(session_id, [])
        results = []
        for item in session_traces:
            # 动态将 Tick 偏移为现实 Now 的前端时间
            aligned_time = self.aligner.align_timestamp(item["tick"], real_now)
            results.append({
                "trace_id": item["request"].trace_id,
                "timestamp": aligned_time.isoformat(), # 转换为 ISO 字符串
                "request": item["request"]
            })
        return results

