import time
import msgspec
import capnp
capnp.remove_import_hook()
ENTRIES = 100
ITERCNT=10_000
# Evaluate round trip (i.e., serialization and deserialization) time for msgspec
t0 = time.perf_counter()
encoder = msgspec.msgpack.Encoder()
decoder = msgspec.msgpack.Decoder()
for i in range(ITERCNT):
    data = {
        "id": i,
        "name": f"Person {i}",
        "email": f"person{i}@example.com",
        "phones": [{"number": f"555-0123-{j:04d}", "type": "home"} for j in range(12)]
    }
    data = [data for _ in range(ENTRIES)]  # Create a list of 0 identical entries
    encoded = encoder.encode(data)
    assert isinstance(encoded, bytes), "msgspec encoding failed"
    obj = decoder.decode(encoded)
t1 = time.perf_counter()
print(f"msgspec: {t1 - t0:.6f} seconds for {ITERCNT} iterations")
print(f"msgspec: {ITERCNT / (t1 - t0):.2f} ops/sec")
print(f"msgspec: {(t1 - t0) / ITERCNT:.12f} sec/op")
print(f"msgspec: {len(encoded)} bytes per message")

# Evaluate round trip (i.e., serialization and deserialization) time for capnp
addressbook = capnp.load('capnpdefs/addressbook.capnp')
t0 = time.perf_counter()
# Reuse the same Person object for all iterations

for i in range(ITERCNT):
    person = addressbook.Person.new_message(
        id=i,
        name=f"Person {i}",
        email=f"person{i}@example.com"
    )
    person.init('phones', 12)
    for j in range(12):
        person.phones[j].number = f"555-0123-{j:04d}"
        person.phones[j].type = addressbook.Person.PhoneNumber.Type.home
    book = addressbook.AddressBook.new_message()
    book.init('people', ENTRIES)

    for j in range(ENTRIES):
        book.people[j] = person

    data = book.to_bytes_packed()
    assert isinstance(data, bytes), "capnp encoding failed"
    obj = addressbook.AddressBook.from_bytes_packed(data)
t1 = time.perf_counter()
print(f"capnp: {t1 - t0:.6f} seconds for {ITERCNT} iterations")
print(f"capnp: {ITERCNT / (t1 - t0):.2f} ops/sec")
print(f"capnp: {(t1 - t0) / ITERCNT:.12f} sec/op")
print(f"capnp: {len(data)} bytes per message")


# Evaluate round trip (i.e., serialization and deserialization) time for protobuf
from compiled_protos import addressbook_pb2
t0 = time.perf_counter()
for i in range(ITERCNT):
    person = addressbook_pb2.Person()
    person.id = i
    person.name = f"Person {i}"
    person.email = f"person{i}@example.com"
    person.last_updated.GetCurrentTime()  # Set the current time as last updated
    # person.employer = "Company {i}"  # Set employer as an example
    for j in range(12):
        phone = person.phones.add()
        phone.number = f"555-0123-{j:04d}"
        phone.type = addressbook_pb2.Person.PHONE_TYPE_HOME

    book = addressbook_pb2.AddressBook()
    for j in range(ENTRIES):
        thisperson = book.people.add()
        thisperson.CopyFrom(person)

    data = book.SerializeToString()
    assert isinstance(data, bytes), "protobuf encoding failed"
    obj = addressbook_pb2.AddressBook()
    obj.FromString(data)
t1 = time.perf_counter()

print(f"protobuf: {t1 - t0:.6f} seconds for {ITERCNT} iterations")
print(f"protobuf: {ITERCNT / (t1 - t0):.2f} ops/sec")
print(f"protobuf: {(t1 - t0) / ITERCNT:.12f} sec/op")
print(f"protobuf: {len(data)} bytes per message")