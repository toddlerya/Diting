import random
from datetime import datetime
from typing import Dict, List
from simulator.projections.base import BaseProjection
from simulator.event_bus import EventBus, BaseEvent
from simulator.clock import SimulationClock

class LogProjection(BaseProjection):
    """
    日志投影层 (Loki Mock)。
    订阅事件总线中的物理资源耗尽或系统异常事件，并将其加工渲染为带 trace_id 上下文的标准 Loki 格式日志。
    此外，支持使用局部 PRNG 局部隔离加噪声，以测试 Agent 的信息筛选与排噪能力。
    (PRNG 是 Pseudo-Random Number Generator 的缩写，中文意为 “伪随机数生成器”)
    """
    def __init__(self, bus: EventBus, clock: SimulationClock, seed: int = 42, noise_rate: float = 0.001):
        super().__init__(bus, clock)
        # 用剧本分配的随机种子实例化 PRNG，防止多轮评测间干扰，保持确定性
        self.random_gen = random.Random(seed)
        self.noise_rate = noise_rate
        # 内存日志数据库：session_id -> list of log dicts
        self.logs_db: Dict[str, List[dict]] = {}
        # 订阅资源状态异常事件以渲染日志
        self.bus.subscribe("ResourceExhausted", self._handle_event)

    def _handle_event(self, event: BaseEvent):
        """
        异常事件回调。
        仅保存原始事件的关键数据，将渲染格式化推迟至查询期。
        """
        payload = event.payload
        session_id = payload.get("session_id", "default")
        if session_id not in self.logs_db:
            self.logs_db[session_id] = []

        self.logs_db[session_id].append({
            "tick": event.tick,
            "service": event.entity_id,
            "level": event.severity,
            "trace_id": event.trace_id,
            "msg": payload.get("msg", "Unknown Error")
        })

    def query_logs(self, session_id: str, service: str, level: str, real_now: datetime) -> List[str]:
        """
        查询 Loki 日志接口，时间前缀对齐为现实 Now 物理时间。
        """
        session_logs = self.logs_db.get(session_id, [])
        results = []
        for log in session_logs:
            if log["service"] == service and log["level"] == level:
                aligned_time = self.aligner.align_timestamp(log["tick"], real_now)
                log_line = f"[{aligned_time.isoformat()}] [{log['level']}] [trace_id: {log['trace_id']}] {log['service']}: Failed due to {log['msg']}"
                results.append(log_line)

        # 仅当查询条件是 WARNING 级别时，才混入 WARNING 噪点日志以防污染其他级别。
        # 实时噪点的日志时间也使用 real_now 动态对齐。
        if level == "WARNING" and self.random_gen.random() < self.noise_rate:
            noise_time = real_now  # 直接绑定为物理实时 Now 或者是指定偏移时间
            noise_line = f"[{noise_time.isoformat()}] [WARNING] [trace_id: None] {service}: Transient connection jitter (noise)"
            if session_id not in self.logs_db:
                self.logs_db[session_id] = []
            results.append(noise_line)

        return results



