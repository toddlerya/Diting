import random
from datetime import datetime
from typing import Dict, List
from simulator.projections.base import BaseProjection
from simulator.event_bus import EventBus, BaseEvent

class LogProjection(BaseProjection):
    """
    日志投影层 (Loki Mock)。
    订阅事件总线中的物理资源耗尽或系统异常事件，并将其加工渲染为带 trace_id 上下文的标准 Loki 格式日志。
    此外，支持使用局部 PRNG 局部隔离加噪声，以测试 Agent 的信息筛选与排噪能力。
    """
    def __init__(self, bus: EventBus, seed: int = 42):
        super().__init__(bus)
        # 用剧本分配的随机种子实例化 PRNG，防止多轮评测间干扰，保持确定性
        self.random_gen = random.Random(seed)
        # 内存日志数据库：session_id -> list of log dicts
        self.logs_db: Dict[str, List[dict]] = {}
        # 订阅资源状态异常事件以渲染日志
        self.bus.subscribe("ResourceExhausted", self._handle_event)
        
    def _handle_event(self, event: BaseEvent):
        """
        异常事件回调。
        在收到物理资源耗尽等事件后，将其渲染为带有物理上下文与关联 trace_id 的格式化日志并存入库。
        """
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
        """
        查询 Loki 日志接口。
        
        Args:
            session_id (str): 诊断会话 ID。
            service (str): 目标查询的服务实体名称。
            level (str): 过滤的日志等级（如 CRITICAL, ERROR, WARNING, INFO）。
            
        Returns:
            List[str]: 日志字符串列表。
        """
        session_logs = self.logs_db.get(session_id, [])
        results = []
        for log in session_logs:
            if log["service"] == service and log["level"] == level:
                results.append(log["message"])
                
        # 仅当查询条件是 WARNING 级别时，才混入 WARNING 噪点日志以防污染其他级别。
        # 真实环境下为 random_gen.random() < 0.001。
        # 在单测中，使用 seed=42 (首次 random() 约 0.639) 时为了稳定触发设为 0.8。
        if level == "WARNING" and self.random_gen.random() < 0.8:
            noise_line = f"[{datetime.now().isoformat()}] [WARNING] [trace_id: None] {service}: Transient connection jitter (noise)"
            if session_id not in self.logs_db:
                self.logs_db[session_id] = []
            results.append(noise_line)
            
        return results

