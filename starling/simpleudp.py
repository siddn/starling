import socket
import threading

import psutil
import ipaddress

LOCALHOST = '127.0.0.1'

def get_ips():
    """Get the local IPV4 addresses of the machine."""
    hostname = socket.gethostname()
    return {*socket.gethostbyname_ex(hostname)[2], LOCALHOST}

def get_broadcast_addresses():
    broadcast_addresses = set()

    for interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address != '127.0.0.1':
                ip = addr.address
                netmask = addr.netmask
                if ip and netmask:
                    network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                    if network.is_link_local:
                        continue
                    broadcast_addresses.add(str(network.broadcast_address))
    
    return broadcast_addresses

class UDPBroadcaster():
    def __init__(self, port=5005):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.port))
        self.broadcast_addrs = get_broadcast_addresses()

    def send(self, message):
        """Broadcast a message to the network."""
        for addr in self.broadcast_addrs:
            self.sock.sendto(message.encode('utf-8'), (addr, self.port))

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