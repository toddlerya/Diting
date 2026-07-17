from datetime import datetime, timedelta

class SimulationClock:
    def __init__(self, start_time: datetime, step_duration: timedelta = timedelta(milliseconds=100)):
        self.start_time = start_time
        self.step_duration = step_duration
        self.current_tick = 0
        
    def tick(self):
        self.current_tick += 1
        
    def now(self) -> datetime:
        return self.start_time + self.current_tick * self.step_duration

class TimeAligner:
    def __init__(self, clock: SimulationClock):
        self.clock = clock
        
    def align_timestamp(self, tick: int, real_now: datetime) -> datetime:
        total_ticks = self.clock.current_tick
        offset_ticks = total_ticks - tick
        return real_now - offset_ticks * self.clock.step_duration
