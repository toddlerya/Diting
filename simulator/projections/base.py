from simulator.event_bus import EventBus
from simulator.clock import SimulationClock, TimeAligner

class BaseProjection:
    """
    投影层基类。
    所有特定的投影层（如时序指标、日志、分布式追踪、Alertmanager 告警）均继承自该类，
    并通过订阅事件总线 (EventBus) 收集 World State Engine 抛出的事件来进行多维状态投影。
    """
    def __init__(self, bus: EventBus, clock: SimulationClock):
        """
        初始化基础投影层。

        Args:
            bus (EventBus): 事件总线，用于订阅仿真中产生的各种事件。
            clock (SimulationClock): 仿真时钟，用于管理和推移虚拟仿真时间。
        """
        self.bus = bus
        self.clock = clock
        self.aligner = TimeAligner(clock)


