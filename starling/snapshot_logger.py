from starling import NexusSubscriber
from threading import Thread
from queue import Queue
import atexit
import msgspec
import datetime
import time
import gzip


class SnapshotCollector:
    def __init__(self, topic: str = "snapshot", decode_function: callable = msgspec.json.decode):
        """A class to collect and store snapshots from a specific topic. The topic can be a wildcard
        as normal, however all topics MUST be able to be deserialized with the same function into a dict. Additionally,
        the snapshots are stored in a queue, and written sequentially. There is no guarantee that snapshots will be logically coherant
        if you mix different topics. Thus, it is recommended that the snapshots be exclusive to a single topic.

        Args:
            topic (str, optional): The topic to subscribe to for snapshots. Defaults to "snapshot".
            decode_function (callable, optional): The function to use for decoding messages. Defaults to msgspec.json.decode.
        """
        self.snapshot_topic: str = topic
        self.snapshots: Queue[dict] = Queue()
        self.sub = NexusSubscriber()
        self.encoder = msgspec.json.Encoder()
        self.sub.subscribe(self.snapshot_topic, lambda msg, topic: self.snapshots.put(decode_function(msg)))
        self.fhandle = None
        self.writet = None
        atexit.register(self.stop)

    def put(self, snapshot: dict):
        self.snapshots.put(snapshot)

    def writer_thread(self):
        while True and self.fhandle:
            entry = self.snapshots.get()
            if entry == "STOPWRITE":
                break
            self.fhandle.write(self.encoder.encode(entry) + b'\n')

    def start(self, file_name: str = None):
        while not self.sub.nexus:
            time.sleep(0.1)
        if file_name is None:
            file_name = f"{datetime.datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}_snapshot.jsonl.gz"
        self.snapshots.queue.clear()
        self.fhandle = gzip.open(file_name, "ab", compresslevel=6)
        self.writet = Thread(target=self.writer_thread, daemon=True)
        self.writet.start()

    def stop(self):
        self.snapshots.put("STOPWRITE")
        self.writet.join()
        if self.fhandle:
            self.fhandle.close()


def _main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--topic", "-t", type=str, default="snapshot", help="The topic to subscribe to for snapshots")
    parser.add_argument("--file", "-f", type=str, default=None, help="The file to write snapshots to")
    parser.add_argument("--duration", "-d", type=float, default=None, help="The duration to run the snapshot logger")
    args = parser.parse_args()

    collection = SnapshotCollector(topic=args.topic)
    file_name = args.file
    if file_name and not file_name.endswith(".jsonl.gz"):
        file_name += ".jsonl.gz"
    collection.start(file_name=file_name)
    if args.duration:
        time.sleep(args.duration)
    else:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    collection.stop()

if __name__ == "__main__":
    _main()