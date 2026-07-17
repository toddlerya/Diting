from simulator.event_bus import EventBus

class BaseProjection:
    def __init__(self, bus: EventBus):
        self.bus = bus
