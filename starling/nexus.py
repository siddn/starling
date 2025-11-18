# Implements a simple nexus node, that can be used for all nodes to discover the available services and topics on this network.
import zmq
import threading
import time
import starling.simpleudp
import socket
import signal
import atexit
from rich import print as print
import uuid

PUB_PORT = 8989
SUB_PORT = 9898
NEXUS_PORT = 8899
OBSERVER_PORT = 9988
GOOGLE_DNS = '8.8.8.8'

def get_local_ip():
    """Get the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # This doesn't need to be a valid address, just needs to be a non-local address
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception as e:
        print(f"Error occurred while getting local IP: {e}")
    finally:
        s.close()


class StarlingNexus():
    def __init__(self, ctx: zmq.Context=None, heartbeat_interval: int=1, echo=False, identifier: str=None):
        self.ctx = zmq.Context.instance() if ctx is None else ctx
        self.xpub = self.ctx.socket(zmq.XPUB)
        self.xsub = self.ctx.socket(zmq.XSUB)

        self.xpub.bind(f'tcp://*:{PUB_PORT}')
        self.xsub.bind(f'tcp://*:{SUB_PORT}')
        # Construct UUID and take first 8 characters - Should be sufficient for most use cases
        # TODO: Maybe a better method to avoid collisions? Though this seems unlikely.
        self.myid = identifier if identifier else str(uuid.uuid4())[:8] 
 
        # Set up a socket pair for the observer
        self.observer_in = self.ctx.socket(zmq.PAIR)
        self.observer_out = self.ctx.socket(zmq.PAIR)
        self.observer_in.linger = self.observer_out.linger = 0
        self.observer_in.hwm = self.observer_out.hwm = 1
        self.observer_in.bind(f"tcp://*:{OBSERVER_PORT}")
        self.observer_out.connect(f"tcp://localhost:{OBSERVER_PORT}")

        self.control = self.ctx.socket(zmq.PAIR)
        self.control.bind(f"inproc://control")

        if not echo:
            self.observer_in = self.observer_out = None

        self.beacon = starling.simpleudp.UDPBroadcaster(port=NEXUS_PORT)
        self.heartbeat_interval = heartbeat_interval

        self.exit_event = threading.Event()


    def heartbeat(self):
        """Broadcasts a heartbeat message to announce the presence of this nexus node."""
        while not self.exit_event.is_set():
            try:
                self.beacon.send(f"{PUB_PORT} {SUB_PORT} {self.myid}")
            except Exception as e:
                print(f"Error occurred in heartbeat: {e}")
                break
            time.sleep(1)


    def observe(self):
        """Echoes messages received from the observer socket."""
        # Set recv timeout to avoid blocking indefinitely
        self.observer_out.setsockopt(zmq.RCVTIMEO, 500)
        while not self.exit_event.is_set():
            try:
                msg = self.observer_out.recv()
                print(f"Echoing message from observer: {msg}")
            except zmq.ContextTerminated:
                print("Context terminated, stopping observer!")
                break
            except zmq.Again:
                # No message received, continue to the next iteration
                continue
            except Exception as e:
                print(f"Error in echoing observer message: {e}")
                break

    def stop(self):
        """Stops the nexus node and cleans up resources."""
        if self.exit_event.is_set(): return
        print("[dark_orange]Stopping nexus node[/dark_orange]...")
        self.exit_event.set()

        print("[dark_orange]Stopping heartbeat thread[/dark_orange]...")
        self.heartbeat_thread.join()
        self.beacon.sock.close()

        print("[dark_orange]Stopping proxy thread[/dark_orange]...")
        _control = self.ctx.socket(zmq.PAIR)
        _control.connect("inproc://control")
        _control.send(b"TERMINATE")
        self.proxy_thread.join()
        
        self.xpub.close()
        self.xsub.close()

        if self.observer_thread:
            print("[dark_orange]Stopping observer thread[/dark_orange]...")
            self.observer_thread.join()
            self.observer_in.close()
            self.observer_out.close()
        self.control.close()
        _control.close()

        self.ctx.term()

        print("[dark_sea_green2]Nexus successfully shut down![/dark_sea_green2]")

    def run(self):
        # Proxying the XSUB and XPUB sockets -> Allows for all subscriber and publishers to connect to a central point
        if self.observer_in:
            self.observer_thread = threading.Thread(target=self.observe, args=(), daemon=True)
            self.observer_thread.start()
            print(f"Observer thread started on port {OBSERVER_PORT} as a PAIR socket.")
        else:
            self.observer_thread = None
        self.proxy_thread = threading.Thread(target=zmq.proxy_steerable, args=(self.xsub, self.xpub, self.observer_in, self.control), daemon=True)
        # Hearbeat Beaconing - UDP broadcast periodically to announce the presence of this beacon node, subsciptions and publications can me made aware of this beacon's ip address.
        self.heartbeat_thread = threading.Thread(target=self.heartbeat, args=(), daemon=True)

        self.proxy_thread.start()
        self.heartbeat_thread.start()

        signal.signal(signal.SIGINT, lambda signum, frame: self.stop())
        signal.signal(signal.SIGTERM, lambda signum, frame: self.stop())
        atexit.register(self.stop)
        starlinglogo = """
┏┓     ┓•    
┗┓╋┏┓┏┓┃┓┏┓┏┓
┗┛┗┗┻┛ ┗┗┛┗┗┫
            ┛
"""
        print(starlinglogo.strip())
        print("[light_steel_blue]Starling Nexus node running. Press Ctrl+C to stop.")
        try:
            while True:
                self.exit_event.wait(0.5) # seconds
                if self.exit_event.is_set():
                    break
        except KeyboardInterrupt:
            pass
        finally:
            return


def _main():
    """Main function to run the Starling Nexus."""
    import argparse
    parser = argparse.ArgumentParser(description=
        """
        Run the Starling Nexus. This is the central node that allows other publishers and subscribers to discover and talk to each other. All messages
        are routed through this node, and it provides a heartbeat mechanism to announce its presence on the network. If the nexus ever dies, messages will not
        be routed, though this will be a quiet death and no error will be raised. Have external mechanisms for monitoring the overall state of your setup.
        """
        )
    parser.add_argument('--echo', action='store_true', help="Echo messages received from the observer socket. Useful for debugging, but bad under high load.")
    echo = parser.parse_args().echo
    nexus = StarlingNexus(echo=echo)
    nexus.run()

if __name__ == "__main__":
    # Example usage of the Nexus class
    _main()