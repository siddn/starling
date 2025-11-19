import time
from starling import NexusPublisher
from starling import msgspec

publisher = NexusPublisher()
i = 0
while True:
    publisher.send("snapshot", msgspec.json.encode({'time': time.perf_counter() , 'index': i}))
    time.sleep(0.0001)
    i += 1