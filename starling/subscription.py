import zmq
import socket
import time
import starling.simpleudp
import threading
import atexit
from queue import Queue
import queue
import re

TINY=10
SMALL=1_000
MEDIUM=10_000
LARGE=100_000_000_000

LOCALHOST = '127.0.0.1'

TOPIC_DELIM_CHAR = '.'

VALID_TOPIC_PATTERN = re.compile(r'^(([^.#*]+)|[*#])(\.([^.#*]+|[*#]))*$')

def get_ips():
    """Get the local IPV4 addresses of the machine."""
    hostname = socket.gethostname()
    return {*socket.gethostbyname_ex(hostname)[2], LOCALHOST}


def validate_topic(topic: str):
    """Validate the topic name according to the rules:
    1. Topic names cannot be empty.
    2. Topic names cannot contain multiple consecutive prefix characters.
    3. Topic names cannot start or end with a prefix character.
    4. Topic names cannot include wildcards if they are not within a valid context. They must be at the start or end, or enclosed by prefix characters.
    5. UTF-8 characters only
    """
    return bool(VALID_TOPIC_PATTERN.match(topic))


def to_regex(topic: str):
    """Convert a topic string with wildcards to a regex pattern."""
    escaped = re.escape(topic)  # Escape all special characters
    # * represents 1 or more groups of characters
    escaped = escaped.replace(r'\*', r'[^.]+')  # Replace * with [^.]+

    escaped = escaped.replace(r'\.\#', r'(?:\.[^.]+)*')  # Replace # with (?:\.[^.]+)*
    escaped = escaped.replace(r'\#\.', r'(?:[^.]+\.)*')  # Replace # with [^.]+(\.|$)*
    escaped = escaped.replace(r'\#', r'.*')

    return re.compile(f'^{escaped}$')

# For the nexus subscriber, we assume that there is one or more nexuses that is aggregating messages from multiple publishers. We will connect to the nexus's XPUB socket and listen for messages on subscribed topics. The nexus will also broadcast its presence via UDP.
class NexusSubscriber():
    """A subscriber class that expects a nexus node which broadcasts its presence via UDP and allows subscribing to topics.
    The subscriber connects to the nexus's XPUB socket and listens for messages on subscribed topics. The "true" publishers are
    unknown to the subscriber, but they are expected to publish messages to the nexus's XPUB socket. These are then routed out to the
    subscriber and the subscriber can process them via callbacks. Each topic can be registered with a callback function that will be called
    whenever a message is received on that topic. The subscriber also listens for UDP broadcasts from the nexus.
    """
    def __init__(self, ctx: zmq.Context=None, queue_size: int=MEDIUM):
        self.ctx = ctx if ctx else zmq.Context.instance()
        self.sub = self.ctx.socket(zmq.SUB)
        self.udp = starling.simpleudp.UDPBroadcaster(port=8899)
        self.poller = zmq.Poller()
        self.poller.register(self.sub, zmq.POLLIN)
        self.poller.register(self.udp.sock, zmq.POLLIN)

        self.nexus = {}
        self.subscriptions = {}
        self.wildcard_subs = [] # list of tuples (topic, regex) for wildcard subscriptions -> used to iterate through a smaller subset of subscriptions

        self.myips = set(get_ips())

        self.running = True
        self.queue_size = queue_size
        # kick off the recv loop thread, which will handle incoming messages and UDP broadcasts.
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()

        atexit.register(self.stop)

    def _recv_loop(self):
        """The main loop that listens for messages on the subscribed topics and UDP broadcasts from the nexus."""
        while self.running:
            socks = dict(self.poller.poll(500)) # Poll for events with a timeout of 500ms -> Allows for exit handlers to kill this thread
            if self.sub in socks: # Check if there are messages on the subscriber socket
                try:
                    message = self.sub.recv_multipart(flags=zmq.NOBLOCK)
                    if not message or len(message) != 2: continue  # Skip if the message is empty or malformed
                    topic: str = message[0].decode('utf-8')
                    data: bytes = message[1]

                    if topic in self.subscriptions:
                        try:
                            assert data!=None, "Received None data from the publisher"
                            self.subscriptions[topic]['queue'].put_nowait((data, topic))
                        except queue.Full: pass

                    for wc, regex in self.wildcard_subs:
                        if regex.match(topic):
                            try:
                                assert data!=None, "Received None data from the publisher"
                                self.subscriptions[wc]['queue'].put_nowait((data, topic))
                            except queue.Full: pass
                except zmq.Again:
                    pass

            if self.udp.sock.fileno() in socks: # Check if there are UDP broadcasts from the nexus
                message, addr = self.udp.recv()
                # Check if we already know about this nexus
                if addr in self.nexus:
                    if self.nexus[addr] == tuple(message.split(' ')):
                        continue
                self.nexus.update({addr: tuple(message.split(' '))})
                self._connect_to_nexus()

    def _connect_to_nexus(self):
        for addr in self.nexus:
            con_addr = LOCALHOST if addr[0] in self.myips else addr[0]
            self.sub.connect(f"tcp://{con_addr}:{self.nexus[addr][0]}")

    def _topic_listen(self, topic: str):
        """Thread function to handle messages for a specific topic via a callback"""
        cb: callable = self.subscriptions[topic]['cb']
        q: Queue = self.subscriptions[topic]['queue']
        while self.running:
            msg, recv_topic = q.get()
            if msg is None: return  # Exit if None is put in the queue
            cb(msg, recv_topic)

    def subscribe(self, topic: str, callback: callable):
        if not validate_topic(topic):
            raise ValueError(f"Invalid topic name: {topic}, please ensure it does not start or end with a '.', doesn't contain consecutive '.' characters, and does not contain wildcards in invalid contexts.")

        q = Queue(maxsize=self.queue_size)
        t = threading.Thread(target=self._topic_listen, args=(topic,), daemon=True)
        if ('*' in topic) or ('#' in topic):
            r = to_regex(topic)
            # Subscribe to the topic, making sure to subscribe to the highest level namespace before the wildcard
            first_single_wildcard = topic.find('*')
            first_multi_wildcard = topic.find('#')
            first_wildcard = min(first_single_wildcard, first_multi_wildcard) if first_single_wildcard != -1 and first_multi_wildcard != -1 else max(first_single_wildcard, first_multi_wildcard)
            if first_wildcard > 0:
                zmq_topic = topic[:first_wildcard-1]
            else: # Special case for a prefix wildcard subscription, this requires us to subscribe to all topics and manually filter.
                print("Specially subscribing to all topics for wildcard subscription")
                zmq_topic = ''
        else:
            r = None
            zmq_topic = topic

        self.sub.setsockopt_string(zmq.SUBSCRIBE, zmq_topic)
        subscription_info = {'cb': callback, 'queue': q, 'thread': t, 'regex': r}
        self.subscriptions[topic] = subscription_info
        if r is not None:
            self.wildcard_subs.append((topic, r))
        t.start()

    def unsubscribe(self, topic: str):
        if topic in self.subscriptions:
            self.sub.setsockopt_string(zmq.UNSUBSCRIBE, topic)
            self.subscriptions[topic]['queue'].put((None, None))
            self.subscriptions[topic]['thread'].join()
            del self.subscriptions[topic]
            for wc, regex in self.wildcard_subs:
                if wc == topic:
                    self.wildcard_subs.remove((wc, regex))
                    break

    def stop(self):
        for topic in list(self.subscriptions.keys()):
            self.unsubscribe(topic)
        self.running = False
        self.recv_thread.join()
        self.sub.close()
        self.udp.sock.close()
        self.ctx.term()

class TempDataClass():
    def __init__(self, msg: str, topic: str):
        self.msg = msg
        self.topic = topic
        self.stamps = []

    def update(self, msg: str, topic: str):
        self.msg = msg
        self.topic = topic
        self.stamps.append(time.time())  # Update the timestamp to the current time

if __name__ == "__main__":
    sub = NexusSubscriber(queue_size=LARGE)

    holder = TempDataClass(msg=None, topic=None)

    sub.subscribe('topics.#', holder.update)
    while True:
        time.sleep(1)
        print(holder.msg, holder.topic)


    # Test Regex matching
    

    # subscription = '#.foo.bar.*.#'
    # print(validate_topic(subscription))
    # pattern = to_regex(subscription)
    # print(pattern)
    # topics = [
    #     "foo",
    #     "foo.bar",
    #     "foo.bar.baz",
    #     "foo.bar.buz.baz",
    #     "foobar",
    #     "foo_bar.baz",
    #     "foo..bar", # Invalid, should not match
    #     "foo.", # Invalid, should not match
    #     "foo.bar.", # Invalid, should not match
    #     "foo.bar/baz"
    # ]

    # print("Testing wildcard validation:")
    # for topic in topics:
    #     print(f'{topic:15} -> Match: {bool(pattern.match(topic))}')
