from datetime import datetime, timedelta


class SimulationClock:
    """
    仿真时钟管理类。
    用于在离线 discrete simulation 过程中以离散步长推进全局虚拟时间轴。
    """

    def __init__(
        self, start_time: datetime, step_duration: timedelta = timedelta(milliseconds=100)
    ):
        """
        初始化仿真时钟。

        Args:
            start_time (datetime): 仿真虚拟启动时刻。
            step_duration (timedelta): 每一个 tick 代表的仿真步长（默认 100ms）。
        """
        self.start_time = start_time
        self.step_duration = step_duration
        self.current_tick = 0

    def tick(self):
        """推进时钟，当前 tick 自增 1。"""
        self.current_tick += 1

    def now(self) -> datetime:
        """返回当前 tick 对应的仿真虚拟 datetime。"""
        return self.start_time + self.current_tick * self.step_duration


class TimeAligner:
    """
    时间戳对齐器。
    用于在仿真运行完毕后，将离线 Tick 的时间轴动态映射到发起评测的瞬间物理时间 (Real Now)，
    避免 MCP Client 进行相对时间查询（如 [5m]）时发生历史时间不匹配而查出空数据的问题。
    """

    def __init__(self, clock: SimulationClock):
        self.clock = clock

    def align_timestamp(self, tick: int, real_now: datetime) -> datetime:
        """
        将指定的 tick 转换为对齐 real_now 物理现实时间的 datetime。

        计算逻辑：
        1. 找出最后一个 tick 的总步长。
        2. 根据当前 tick 距最后一个 tick 的差值，向前做负偏移。

        Args:
            tick (int): 要转换的仿真 tick。
            real_now (datetime): 当前发起评测的时刻物理 Now 时间戳。

        Returns:
            datetime: 映射对齐后的物理时刻。
        """
        total_ticks = self.clock.current_tick
        offset_ticks = total_ticks - tick
        return real_now - offset_ticks * self.clock.step_duration
