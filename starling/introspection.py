from starling.subscription import NexusSubscriber
import msgspec
import time
from rich.console import Console
from rich.theme import Theme
from rich.json import JSON
import rich
theme = Theme({
    "json.key": "bold cornflower_blue",   # JSON keys
    "json.string":    "bold magenta",        # JSON string *values* (modern)
    "string":         "bold magenta",        # alternate token name (older or different path)
    "repr.str":       "bold magenta",        # Python repr strings
    "json.number": "bold medium_spring_green",  # JSON numbers
    "json.boolean": "bold yellow",        # true / false
    "json.null": "dim", 
})
console = Console(theme=theme)

def _echo():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("topic", type=str, help="The topic to echo")
    args = parser.parse_args()
    echo(args.topic)

def echo(topic, deserialize=msgspec.json.decode):
    subscriber = NexusSubscriber()
    subscriber.subscribe(topic, lambda msg, topic: console.print(JSON(f"{msgspec.json.format(msg, indent=4).decode('utf-8')}")))
    while True:
        time.sleep(1)


def _frequency():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("topic", type=str, help="The topic to measure frequency on")
    parser.add_argument("--window", type=int, default=1000, help="Window size in frames to average frequency over")
    args = parser.parse_args()
    frequency(args.topic, args.window)

def frequency(topic, window):
    from collections import deque
    import time
    import numpy as np
    subscriber = NexusSubscriber()
    sample_times = deque(maxlen=window)
    subscriber.subscribe(topic, lambda msg, topic: sample_times.append(time.perf_counter()))
    while True:
        time.sleep(1)
        diffs = np.diff(sample_times)
        freq = 1/np.mean(diffs) if len(diffs) > 0 else 0
        rich.print(f'[bold yellow]Frequency:[/] {freq:.4f} Hz over last {len(sample_times)} samples')

def _topics():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, default="#", help="The topic to monitor, use '#' for all topics")
    parser.add_argument("--window", type=int, default=1000, help="Window size in frames to average frequency over")
    args = parser.parse_args()
    topics(args.topic, args.window)

def topics(topicset, window):
    from collections import deque
    import numpy as np
    subscriber = NexusSubscriber()
    all_topics = {}
    subscriber.subscribe(topicset, lambda msg, topic: update_topic_info(msg, topic))
    def update_topic_info(msg, topic):
        current_info = all_topics.get(topic, {'times': deque(maxlen=window), 'count': 0})
        current_info['times'].append(time.perf_counter())
        current_info['count'] += 1
        all_topics[topic] = current_info


    while True:
        time.sleep(1)

        towrite = ""
        for t, info in all_topics.items():
            freq = 1/np.mean(np.diff(info['times'])) if len(info['times']) > 1 else 0
            towrite += f"[bold green]{t:12}[/bold green] - [bold yellow]{freq:.3f} Hz[/bold yellow] - [bold cyan]{info['count']:>5} messages[/bold cyan]\n"
        console.clear()
        console.rule("Starling Topics")
        console.print(towrite.strip())