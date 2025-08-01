import socket
import threading

LOCALHOST = '127.0.0.1'

def get_ips():
    """Get the local IPV4 addresses of the machine."""
    hostname = socket.gethostname()
    return {*socket.gethostbyname_ex(hostname)[2], LOCALHOST}

class UDPBroadcaster():
    def __init__(self, port=5005):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.port))

    def send(self, message):
        """Broadcast a message to the network."""
        self.sock.sendto(message.encode('utf-8'), ('<broadcast>', self.port))
        # self.sock.sendto(message.encode('utf-8'), ('172.29.240.255', self.port))


    def recv(self):
        """Receive a message from the network."""
        data, addr = self.sock.recvfrom(1024)
        return data.decode('utf-8'), addr
    

if __name__ == "__main__":
    caster1 = UDPBroadcaster(port=5005)
    caster2 = UDPBroadcaster(port=5005)

    def broadcast_messages():
        while True:
            try:
                caster1.broadcast("Hello from caster1")
                caster2.broadcast("Hello from caster2")
            except Exception as e:
                return

    def receive_messages():
        while True:
            try:
                message, addr = caster1.receive()
                print(f"caster1 received: {message} from {addr}")
                message, addr = caster2.receive()
                print(f"caster2 received: {message} from {addr}")
            except Exception as e:
                return

    t1 = threading.Thread(target=broadcast_messages, daemon=True)
    t2 = threading.Thread(target=receive_messages, daemon=True)

    t1.start()
    t2.start()

    # Keep the main thread alive
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        caster1.sock.close()
        caster2.sock.close()
        t1.join()
        t2.join()
        print("Broadcasting stopped.")