from typing import Dict, List
from simulator.projections.base import BaseProjection
from simulator.event_bus import EventBus

class MetricProjection(BaseProjection):
    """
    指标投影层 (Prometheus Mock)。
    负责在每个 Tick 周期内，将所有实体产生的物理性能数值记录、汇总，并按会话隔离缓存，
    以提供标准的 Prometheus 范围时序查询接口。
    """
    def __init__(self, bus: EventBus):
        super().__init__(bus)
        # 共享内存缓存数据库：session_id -> metric_name -> list of points
        # 数据点格式：{"tick": int, "value": float}
        self.metrics_db: Dict[str, Dict[str, List[dict]]] = {}
    
    def record_metric(self, session_id: str, metric_name: str, tick: int, value: float):
        """
        向指定的 session_id 下记录特定指标在特定 tick 时的数值。
        """
        if session_id not in self.metrics_db:
            self.metrics_db[session_id] = {}
        if metric_name not in self.metrics_db[session_id]:
            self.metrics_db[session_id][metric_name] = []
        self.metrics_db[session_id][metric_name].append({"tick": tick, "value": value})
        
    def query_metric(self, session_id: str, metric_name: str, start_tick: int, end_tick: int) -> List[dict]:
        """
        查询特定 session_id 下指定时序指标在 tick 区间 [start_tick, end_tick] 的历史曲线。
        """
        session_metrics = self.metrics_db.get(session_id, {})
        points = session_metrics.get(metric_name, [])
        return [pt for pt in points if start_tick <= pt["tick"] <= end_tick]

