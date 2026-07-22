from datetime import datetime

from simulator.clock import SimulationClock
from simulator.entity import Entity
from simulator.event_bus import BaseEvent, EventBus, EventType
from simulator.projections.base import BaseProjection


class MetricProjection(BaseProjection):
    """
    指标投影层 (Prometheus Mock)。
    负责在每个 Tick 周期内，将所有实体产生的物理性能数值记录、汇总，并按会话隔离缓存，
    以提供标准的 Prometheus 范围时序查询接口。
    """

    def __init__(
        self, bus: EventBus, clock: SimulationClock, entities: dict[str, Entity] | None = None
    ):
        super().__init__(bus, clock)
        # 共享内存缓存数据库：session_id -> metric_name -> list of points
        # 数据点格式：{"tick": int, "value": float}
        self.metrics_db: dict[str, dict[str, list[dict]]] = {}
        self.entities: dict[str, Entity] | None = None
        if entities is not None:
            self.bind_entities(entities)

        # 自动订阅 Trace 结束事件流式提取指标数据
        self.bus.subscribe(EventType.TRACE_FINISHED, self._handle_trace_finished)

    def bind_entities(self, entities: dict[str, Entity]):
        """绑定要监控和录入指标的实体字典。"""
        self.entities = entities

    def _handle_trace_finished(self, event: BaseEvent):
        """当 Request/Trace 演进完成时，自动流式采样录入所有实体的派生指标。"""
        if not self.entities:
            return
        session_id = event.payload.get("session_id", "default")
        for s_id, entity in self.entities.items():
            metrics = entity.derived_metrics()
            for metric_name, val in metrics.items():
                if isinstance(val, int | float):
                    self.record_metric(session_id, f"{s_id}_{metric_name}", event.tick, float(val))

    def record_metric(self, session_id: str, metric_name: str, tick: int, value: float):
        """
        向指定的 session_id 下记录特定指标在特定 tick 时的数值。
        """
        if session_id not in self.metrics_db:
            self.metrics_db[session_id] = {}
        if metric_name not in self.metrics_db[session_id]:
            self.metrics_db[session_id][metric_name] = []
        self.metrics_db[session_id][metric_name].append({"tick": tick, "value": value})

    def query_metric(
        self, session_id: str, metric_name: str, start_tick: int, end_tick: int, real_now: datetime
    ) -> list[dict]:
        """
        查询特定 session_id 下指定时序指标在 tick 区间 [start_tick, end_tick] 的历史曲线，并映射至现实时间。
        """
        session_metrics = self.metrics_db.get(session_id, {})
        points = session_metrics.get(metric_name, [])
        results = []
        for pt in points:
            if start_tick <= pt["tick"] <= end_tick:
                aligned_time = self.aligner.align_timestamp(pt["tick"], real_now)
                results.append({"timestamp": aligned_time.isoformat(), "value": pt["value"]})
        return results
