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
    parser.add_argument("--window", type=int, default=16, help="Window size in frames to average frequency over - Used only for lower frequency topics")
    args = parser.parse_args()
    # topics(args.topic, args.window)
    topics2(args.topic, args.window)

def topics(topicset, window):
    from collections import deque
    import numpy as np
    subscriber = NexusSubscriber()
    all_topics = {}
    subscriber.subscribe(topicset, lambda msg, topic: update_topic_info(msg, topic))
    def update_topic_info(msg, topic):
        current_info = all_topics.get(topic, {'times': deque(maxlen=window), 'count': 0, 'freq': 0})
        current_info['times'].append(time.perf_counter())
        current_info['count'] += 1
        all_topics[topic] = current_info


    while True:
        time.sleep(1)
        
        towrite = ""
        for t, info in all_topics.items():
            last_seen = info['times'][-1] if len(info['times']) > 0 else time.perf_counter()
            est_period = 1/info['freq'] if info['freq'] > 0 else float('inf')
            freq = 1/np.mean(np.diff(info['times'])) if len(info['times']) > 1 else 0

            if (time.perf_counter() - last_seen) > 3 * est_period:
                freq_to_print = 0
                info['times'].clear()
            else:
                freq_to_print = freq
            towrite += f"[bold green]{t:12}[/bold green] - [bold yellow]{freq_to_print:.3f} Hz[/bold yellow] - [bold cyan]{info['count']:>5} messages[/bold cyan]\n"

            info['freq'] = freq
            all_topics[t] = info
        console.clear()
        console.rule("Starling Topics")
        console.print(towrite.strip())


def topics2(topicset, window):
    from collections import deque
    import numpy as np
    import threading
    
    topics_info = {}
    subscriber = NexusSubscriber()
    subscriber.subscribe(topicset, lambda msg, topic: update_topic_info(msg, topic))

    lock = threading.Lock()

    def update_topic_info(msg, topic):
        with lock:
            current_info = topics_info.get(topic, {'total_count': 0, 'count': 0, 'times': deque(maxlen=window), 'est_freq': 0})
            current_info['total_count'] += 1
            current_info['count'] += 1
            current_info['times'].append(time.perf_counter())
        topics_info[topic] = current_info
    
    prev_time = time.perf_counter()
    while True:
        time.sleep(1)
        current_time = time.perf_counter()
        time_delta = current_time - prev_time
        towrite = ""
        for t, info in topics_info.items():
            last_seen = info['times'][-1] if len(info['times']) > 0 else time.perf_counter()

            if info['count'] < 3:
                freq = 1/np.mean(np.diff(info['times'])) if len(info['times']) > 1 else 0
            else:
                freq = info['count'] / time_delta if time_delta > 0 else 0

            est_period = 1/info['est_freq'] if info['est_freq'] > 0 else float('inf')
            if (current_time - last_seen) > 3 * est_period:
                freq_to_print = 0
                info['times'].clear()
            else:
                freq_to_print = freq
    
            towrite += f"[bold green]{t:12}[/bold green] - [bold yellow]{freq_to_print:.3f} Hz[/bold yellow] - [bold cyan]{info['total_count']:>5} messages[/bold cyan]\n"
            info['count'] = 0
            info['est_freq'] = freq
            with lock:
                topics_info[t] = info
        console.clear()
        console.rule("Starling Topics")
        console.print(towrite.strip())
        prev_time = current_time

if __name__ == "__main__":
    topics2("#", 16)