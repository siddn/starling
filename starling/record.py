from starling.subscription import NexusSubscriber
from dataclasses import dataclass, field
from threading import Thread, Lock
import time
import msgspec

@dataclass
class ArbitraryDataStore:
    """A simple data store to hold arbitrary data from any number of topics. Data is stored as frames of dictionaries"""
    data: dict = field(default_factory=dict)

    def update(self, topic: str, frame: dict):
        self.data.setdefault(topic, []).append(frame)


def _main():
    sub = NexusSubscriber()
    ads = ArbitraryDataStore()
    sub.subscribe('', ads.update)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        return