import zmq
import socket
import time
import starling.simpleudp
import threading
import atexit
import re

LOCALHOST = '127.0.0.1'
TOPIC_DELIM_CHAR = '.'

NEXUS_TIMEOUT = 5


VALID_TOPIC_PATTERN = re.compile(r'^(([^.#*]+)|[*#])(\.([^.#*]+|[*#]))*$')

def validate_topic(topic: str):
    """Validate the topic name according to the rules:
    1. Topic names cannot be empty.
    2. Topic names cannot contain multiple consecutive prefix characters.
    3. Topic names cannot start or end with a prefix character.
    4. Topic names cannot include wildcards if they are not within a valid context. They must be at the start or end, or enclosed by prefix characters.
    5. UTF-8 characters only
    """
    return bool(VALID_TOPIC_PATTERN.match(topic))

def get_ips():
    """Get the local IPV4 addresses of the machine."""
    hostname = socket.gethostname()
    return {*socket.gethostbyname_ex(hostname)[2], LOCALHOST}

class NexusPublisher():
    """A publisher class that connects to a nexus node's XSUB socket and publishes messages on subscribed topics.
    The publisher does not broadcast its presence, but it does look for the nexus's presence via UDP.
    """
    def __init__(self, ctx: zmq.Context=None):
        self.ctx = ctx if ctx else zmq.Context.instance()
        self.pub = self.ctx.socket(zmq.PUB)
        self.udp = starling.simpleudp.UDPBroadcaster(port=8899)
        self.poller = zmq.Poller()
        self.poller.register(self.udp.sock, zmq.POLLIN)
        self.running = True

        self.nexus = {}
        self.topics = set()

        self.myips = set(get_ips())

        self.running = True
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()

        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog_thread.start()

        atexit.register(self.stop)

    def _recv_loop(self):
        """The main loop that listens for UDP broadcasts from the Nexus."""
        while self.running:
            socks = dict(self.poller.poll(500)) # Poll for events with a timeout of 500ms -> Allows for exit handlers to kill this thread
            if self.udp.sock.fileno() in socks:
                message, addr = self.udp.recv()
                # Check if we already know about this nexus
                pub_port, sub_port, nexus_id = message.split(' ')
                if nexus_id in self.nexus:
                    self.nexus[nexus_id]['last_seen'] = time.monotonic()
                    continue
                self.nexus.update({nexus_id: {'addr': addr, 'sub_port': sub_port, 'pub_port': pub_port, 'last_seen': time.monotonic()}})
                self._connect_to_nexus()

    def _watchdog_loop(self):
        """Infrequently checks for stale nexus entries and removes them."""
        while self.running:
            time.sleep(1)
            current_time = time.monotonic()
            for nexus_id, info in list(self.nexus.items()):
                if current_time - info['last_seen'] > NEXUS_TIMEOUT:
                    del self.nexus[nexus_id]

    def _connect_to_nexus(self):
        for nexus_id in self.nexus:
            addr = self.nexus[nexus_id]['addr']
            con_addr = LOCALHOST if addr[0] in self.myips else addr[0]
            self.pub.connect(f"tcp://{con_addr}:{self.nexus[nexus_id]['sub_port']}")

    def send(self, topic: str, message: bytes):
        """Publish a message on a specific topic."""
        if not validate_topic(topic):
            raise ValueError(f"Invalid topic: {topic}")
        self.pub.send_multipart([topic.encode('utf-8'), message])

    def stop(self):
        """Stop the publisher and clean up resources."""
        self.running = False
        self.recv_thread.join()
        # self.watchdog_thread.join()
        self.pub.close()
        self.udp.sock.close()
        # self.ctx.term()


if __name__ == "__main__":
    import msgspec
    import random
    import math
    import time
    # import win_precise_time as wpt

    publisher = NexusPublisher()
    publisher2 = NexusPublisher()
    idx = 0
    time.sleep(1)  # Wait for the publisher to connect to the nexus
    while True:
        # JSON example
        imu_data = {
            'ts': time.time(),
            'acc': {'x': math.sin(time.time()), 'y': random.random()*2, 'z': random.random()*2},
            'gyro': {'x': random.random()*2, 'y': random.random()*2, 'z': random.random()*2},
            'mag': {'x': random.random()*2, 'y': random.random()*2, 'z': random.random()*2},
            'orient': {'w': 1.0, 'x': 0.0, 'y': 0.0, 'z': 0.0},
            'idx': idx
        }
        idx += 1
        publisher.send('imu.thigh.data', msgspec.json.encode(imu_data))
        # if idx > 400_000:
        #     break
        # wpt.sleep(.5)
        time.sleep(0.5)
    print("DONE")