from collections.abc import Callable
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """
    仿真事件类型常量枚举。
    继承 str 以保证与标准字符串比较及序列化的兼容性。
    """

    TRACE_FINISHED = "TraceFinishedEvent"
    GENERIC = "Generic"
    RESOURCE_EXHAUSTED = "ResourceExhausted"
    METRIC_THRESHOLD_EXCEEDED = "MetricThresholdExceeded"
    METRIC_THRESHOLD_RECOVERED = "MetricThresholdRecovered"


class EventSeverity(str, Enum):
    """
    仿真事件严重程度常量枚举。
    继承 str 以保证与标准字符串比较及序列化的兼容性。
    """

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class BaseEvent:
    """
    仿真事件基类。
    用于封装仿真过程中产生的各类事件的通用属性。
    """

    def __init__(
        self,
        event_id: str,
        tick: int,
        timestamp: datetime,
        entity_id: str,
        severity: EventSeverity | str,
        event_type: EventType | str,
        payload: dict,
        trace_id: str | None = None,
    ):
        """
        初始化基础事件。

        Args:
            event_id (str): 事件唯一标识。
            tick (int): 事件发生时的仿真步数。
            timestamp (datetime): 事件发生的仿真虚拟时间戳。
            entity_id (str): 触发事件的仿真实体ID。
            severity (Union[EventSeverity, str]): 事件严重程度。
            event_type (Union[EventType, str]): 事件类型，用于 EventBus 订阅和分发。
            payload (dict): 事件所携带的业务数据负载。
            trace_id (Optional[str], optional): 调用链追踪ID。默认为 None。
        """
        self.event_id = event_id
        self.tick = tick
        self.timestamp = timestamp
        self.entity_id = entity_id
        self.severity = severity
        self.event_type = event_type
        self.payload = payload
        self.trace_id = trace_id


class EventBus:
    """
    事件总线类。
    用于管理仿真系统中的事件订阅（Subscribe）与事件发布（Publish），实现组件间解耦。
    """

    def __init__(self):
        """初始化事件总线，构建空的订阅关系表。"""
        self._subscribers: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: EventType | str, callback: Callable):
        """
        订阅指定类型的事件。

        Args:
            event_type (Union[EventType, str]): 要订阅的事件类型名称或枚举。
            callback (Callable): 事件触发时的回调处理函数。该函数需接收一个 BaseEvent 实例作为参数。
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def publish(self, event: BaseEvent):
        """
        发布事件，广播通知所有订阅了该事件类型的回调处理函数。

        Args:
            event (BaseEvent): 被发布的事件实例。
        """
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            handler(event)
