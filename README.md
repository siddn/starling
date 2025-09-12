For now primary goal, work on topic/service discovery. Might use zyre? or custom rolled something or other. For now, use JSON or msgpack to serialize, but next step after that is serialization -> could use Protobufs or flatbuffers or something similar. For JSON packing use msgspec.

Start with a broker based approach. One node will work as the node for all others to register with, and their topics will be subscribed to through this node. Likely gonna use the XPUB/XSUB appraoch, maybe with some other sockets.

After discovery, graceful message recieving and calling back. Will use async polling to reduce load.

In general, this library is suited to a large number of topics (on the order of approximately 1000. Using more and more wildcard matches can make the process slower, so avoid using massive numbers of wildcard subscriptions). If you do use the wildcard subscriptions, use them as intended, i.e. match the most similar logic you can to one subscription.

Deciding on a serialization schema

Likely not Cap'n proto. May be conceptually better, but the actual in language use is pretty un-ergonomic :(.

Probably will use Protobufs? Just found out about bebop could be cool. msgspec is also just easy and schema-free.

Right now we're just going to run with user-defined serialization -> all callback functions and "send" operations expect bytes only

big todo, establish "stale" heartbeats with the nexus. If no nexuses are live, the user should be able to act on that.

## Quickstart
```console
pip install git+https://github.com/siddn/starling.git
```
1. Start the nexus process in a seperate terminal. `starling-nexus`
2. Add a basic publisher to a file
```python
from starling import NexusPublisher
import time
import msgspec

pub = NexusPublisher()

while True:
  pub.send("mytopic", msgspec.json.encode({'time': time.perf_counter(), 'data': 'helooo'})
  time.sleep(1)
```
4. Add a basic subscriber to a file
```python
from starling import NexusSubscriber
import time
import msgspec

sub = NexusSubscriber()
sub.subscribe("mytopic", lambda msg, topic: print(f'{topic}, {msgspec.json.decode(msg)}'))
while True:
  time.sleep(1)
  
```
5. Run both of these to see basic behavior
6. To try snapshot collecting (rosbag counterpart), in a fourth terminal run the following.
```console
starling-snapshot --help
starling-snapshot -t mytopic
```
you should end up with a gzipped JSON lines file. Extract the compressed file to view the saved data.

## Topics
Topics are like a "channel" which messages can be sent to. Topics can be published to from multiple places and subscribed to from multiple places (see below). For "topic paths" use a period for delimitting (ex. `mytopic.subtopic.subsubtopic`).
For subscriptions, you can wildcard with `*` or `#`. `*` will fill to any single topic name (`mytopic.*` will match to `mytopic.subtopic1` but not `mytopic.subtopic1.subsubtopic`)
The `#` will expand to any number of chained topics (or none!). Thus `#` is an alias for every topic.

## Publishing & Subscribing
Any publisher can send any given message on any given topic. This allows a tremendous amount of flexibility, but can be a pretty big footgun if you don't make sure to appropriately handle messages that may have different forms and come from different processes.

### Publishers
A publisher can be created via `pub = starling.NexusPublisher`. To send a message, you simply need to call `pub.send('mytopic', msg)`, where the msg is a bytes object. Now, in all the examples, JSON is used as the serialization format, as there are efficient libraries for coverting dicts to JSON and back in python. It is also easily human readable and provides an easy schema-less logging solution. However, you can serialize using any sort of messaging you care to (protobufs, flatbuffers, msgpack, etc.). In terms of actual operation, when a message is "sent" it is handed off to a zeromq socket, which publishes the message to be recieved by the XSUB socket (handled by the `starling-nexus`), and routed out via an XPUB to any interested subscribers. This means that there is some hopping and a theoretical asyncronicity to the messaging that can impact coordination. This is rarely a practical limitation, but if you are acutely interested in when an event happened, including a timestamp in you message as one of the fields is crucial.

### Subscribers
Subscribers, like publishers, can recieve from multiple topics. Subscribers work on a callback system.
```python
def mycb(mg, topic):
    print(f'{msg} heard from {topic}')

sub = starling.NexusSubscriber()
sub.subscribe("mytopic", mycb)
```
Each callback must accept a `msg` and `topic` argument. If you want to add additional arguments, this must be done via a lambda or other wrapper function. In this way you can specify arguments to be included. If you would like to have persistent information, use an object or dict, which can be passed by address.

## Introspection and Tooling
Starling has not build tools or build step. Right now everything exists as a pure dependency for its respective language (i.e. a Python module).
We do however include some built in tools for debugging and viewing your topics.

#### starling-snapshot
The snapshot tool allows for automatic logging of a topic to a file. Right now, the topic must be published as a JSON serializable message (as in the example above). 
The topic will be logged into a gzipped JSON lines file, with each line being a message from that topic.
```python
starling-snapshot --topic mytopic --file myfile
```

#### starling-echo
This will simply echo messages as they come in on a topic
```python
starling-echo topic_name
```

#### starling-frequency
Displays the topic frequency over a specified window (defaults to 1000)
```python
starling-frequency topic_name --window 1000
```

#### starling-topics
This will display all the topics. Optionally can filter by topic paths
```python
starling-topics
# OR
starling-topics --topic mytopic.* 
```
