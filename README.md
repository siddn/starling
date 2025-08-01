For now primary goal, work on topic/service discovery. Might use zyre? or custom rolled something or other. For now, use JSON or msgpack to serialize, but next step after that is serialization -> could use Protobufs or flatbuffers or something similar. For JSON packing use msgspec.

Start with a broker based approach. One node will work as the node for all others to register with, and their topics will be subscribed to through this node. Likely gonna use the XPUB/XSUB appraoch, maybe with some other sockets.

After discovery, graceful message recieving and calling back. Will use async polling to reduce load.

In general, this library is suited to a large number of topics (on the order of approximately 1000. Using more and more wildcard matches can make the process slower, so avoid using massive numbers of wildcard subscriptions). If you do use the wildcard subscriptions, use them as intended, i.e. match the most similar logic you can to one subscription.

Deciding on a serialization schema

Likely not Cap'n proto. May be conceptually better, but use in C/C++ is not great.

Probably will use Protobufs.
