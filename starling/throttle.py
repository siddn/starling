from starling.subscription import NexusSubscriber
from starling.publication import NexusPublisher
from threading import Thread, Event
import atexit
import time

class NexusThrottle:
    def __init__(self, topic_in: str, topic_out: str, rate_out: float):
        raise NotImplementedError("NexusThrottle is not yet implemented.")
        self.sub = NexusSubscriber(topic_in)
        self.sub.subscribe(topic_in, self.set_latest_msg)
        self.pub = NexusPublisher(topic_out)
        self.rate_out = rate_out
        self.timer = TimedLoop(rate_out)
        self.latest_msgs = {}
        self.thread = None
        self.stop_event = Event()
        atexit.register(self.stop)

    def set_latest_msg(self, msg, topic):
        self.latest_msgs[topic] = msg

    def start(self):
        self.thread = Thread(target=self.loop)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join()

    def loop(self):
        while self.timer.sleep() and not self.stop_event.is_set():
            for topic, msg in self.latest_msgs.items():
                self.pub.send(topic, msg)


def _main():
    from argparse import ArgumentParser
    parser = ArgumentParser(description="Throttle messages from one Nexus topic to another at a specified rate. If the specified rate is higher than the incoming message rate, messages will result in duplicates.")
    parser.add_argument("topic_in", type=str, help="Input topic to subscribe to.")
    parser.add_argument("topic_out", type=str, help="Output topic to publish to.")
    parser.add_argument("--rate_out", type=float, default=10.0, help="Rate (Hz) to publish messages to the output topic.")
    args = parser.parse_args()

    print(f"Throttling messages from '{args.topic_in}' to '{args.topic_out}' at {args.rate_out} Hz.")

    throttle = NexusThrottle(args.topic_in, args.topic_out, args.rate_out)
    throttle.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break
    throttle.stop()