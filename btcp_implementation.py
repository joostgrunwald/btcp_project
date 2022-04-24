#!/usr/local/bin/python3
import contextlib
import socket, argparse
from Packet import Header, Packet, Payload
from Receiver import Receiver
from Sender import Sender
from Poster import send_packet, receive_packet
import queue

class Btcp:

    def __init__(self, source, window, timeout):
        """Create a new UDP Receiver.

        Args:
            source: Tuple of source IP and source port
        """
        self.source = source
        self.peer = None
        self.id = 0
        self.synnumber = 0
        self.acknumber = 0
        self.window = window
        self.connected = False
        self.timeout = timeout

        self.retransmissionQueue = queue.PriorityQueue()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1)

        self.receivebuffer = queue.Queue(1000)
        self.receiver = Receiver(self.receivebuffer, self.sock)
        self.sendbuffer = queue.Queue(1000)
        self.sender = Sender(self.sendbuffer, self.sock)

    def start(self):
        self.sock.bind(self.source)
        self.receiver.start()
        self.sender.start()

    def listen(self):
        if self.connected:
            raise Exception("Cannot listen: connection already established!")

        print("Start listening for incoming connections")

        # Wait for handshake
        data, addr = self.receivebuffer.get()
        synpacket = Packet.from_bytes(data)
        if synpacket is None or\
                synpacket.header.syn != 1 or\
                synpacket.header.ack == 1 or\
                synpacket.check_checksum() is False:
            return False

        print(f"Incoming connection from {str(addr)}")

        if synpacket.header.window < self.window:
            self.window = synpacket.header.window
        # Send SYN-ACK
        header = Header(synpacket.header.id, 0, synpacket.header.synnumber + 1, 0b10010, self.window, 0, 0)
        payload = Payload(bytes(1000))
        synackpacket = Packet(header, payload)
        synackpacket.set_checksum()
        self.sendbuffer.put((synackpacket.to_bytes(), addr))

        # Wait for ACK
        with contextlib.suppress(queue.Empty):
            data, addr = self.receivebuffer.get(True, self.timeout)
            ackpacket = Packet.from_bytes(data)
            if ackpacket is None or \
                    ackpacket.header.ack != 1 or \
                    ackpacket.header.syn == 1 or \
                    ackpacket.header.id != synackpacket.header.id or \
                    ackpacket.header.window != self.window or \
                    ackpacket.check_checksum() is False:
                pass

        print(f"Connection established with {str(addr)}")
        self.peer = addr
        self.acknumber = synpacket.header.synnumber + 1
        self.connected = True
        self.id = synackpacket.header.id

        return True

    def connect(self, destination):
        if self.connected:
            raise Exception("Cannot connect: connection already established!")

        print(f"Starting handshake with {str(destination)}")

        # Send SYN
        id = 42
        synnumber = self.synnumber
        header = Header(id, synnumber, 0, 0b10, self.window, 0, 0)
        payload = Payload(bytes(1000))
        synpacket = Packet(header, payload)
        synpacket.set_checksum()
        self.sendbuffer.put((synpacket.to_bytes(), destination))

        # Syn-Ack ontvangen
        try:
            data, addr = self.receivebuffer.get(True, self.timeout)
        except queue.Empty:
            return False

        synackpacket = Packet.from_bytes(data)

        # Controleren of ack = syn+1
        if synackpacket is not None and \
                synackpacket.header.acknumber == synnumber + 1\
                and synackpacket.header.syn == 1\
                and synackpacket.header.ack == 1\
                and synackpacket.header.id == id\
                and synackpacket.check_checksum() is True:
            synnumber = synackpacket.header.acknumber
        else:
            return False

        self.window = synackpacket.header.window

        # Ack sturen naar server
        header = Header(id, 0, synnumber, 0b10000, self.window, 0, 0)
        payload = Payload(bytes(1000))
        ackpacket = Packet(header, payload)
        ackpacket.set_checksum()
        self.sendbuffer.put((ackpacket.to_bytes(), destination))

        print(f"Connection established with {str(destination)}")
        self.peer = destination
        self.synnumber = synnumber
        self.connected = True
        self.id = id

        return True

    def start_termination(self, destination):
        # FIN Packet sturen
        id = 42
        synnumber = self.synnumber
        header = Header(id, synnumber, 0, 0b1, self.window, 0, 0)
        payload = Payload(bytes(1000))
        finpacket = Packet(header, payload)
        finpacket.set_checksum()
        self.sendbuffer.put((finpacket.to_bytes(), destination))

        # FIN-ACK ontvangen
        try:
            data, addr = self.receivebuffer.get(True, self.timeout)
        except queue.Empty:
            return False
        finackpacket = Packet.from_bytes(data)
        if finackpacket is None or finackpacket.header.fin != 1 or finackpacket.header.ack != 1 or addr != destination:
            # print("Termination handshake failed with " + str(destination))
            return False

        # ACK sturen
        header = Header(id, 0, synnumber, 0b10000, self.window, 0, 0)
        payload = Payload(bytes(1000))
        ackpacket = Packet(header, payload)
        ackpacket.set_checksum()
        self.sendbuffer.put((ackpacket.to_bytes(), destination))
        print(f"Connection terminated with {str(destination)}")
        return True

    def respond_termination(self, destination, finpacket):
        # FIN-ACK sturen als FIN packet ontvangen is
        header = Header(finpacket.header.id, 0, finpacket.header.synnumber + 1, 0b10001, self.window, 0, 0)
        payload = Payload(bytes(1000))
        finackpacket = Packet(header, payload)
        finackpacket.set_checksum()
        self.sendbuffer.put((finackpacket.to_bytes(), destination))

        # ACK ontvangen
        try:
            data, addr = self.receivebuffer.get(True, self.timeout)
        except queue.Empty:
            return False
        ackpacket = Packet.from_bytes(data)

        if ackpacket is None or ackpacket.header.ack != 1:
            # print("Termination handshake failed with " + str(destination))
            return False
        print(f"Connection terminated with {str(destination)}")
        return True
