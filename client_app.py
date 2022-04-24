#!/usr/local/bin/python3
import socket, argparse
from Packet import Header, Packet, Payload
import queue
import Btcp
import time
import Runners


class bTCP_client(Btcp.Btcp):

    def __init__(self, source, destination, window, timeout = 10):
        super().__init__(source, window, timeout)
        self.destination = destination
        self.file = None
        self.data = []
        self.filepointer = 0
        self.timelimit = 0
        self.lastack = -1
        self.dupAckQueue = queue.PriorityQueue()

    def begin(self):
        self.start()
        # Start Handshake
        while not self.connected:
            self.connected = self.connect(self.destination)

    def set_file(self, file2):
        self.file = file2
        self.data = file2.to_packets()
        self.filepointer = 0

    def send_file(self):
        if self.file is None:
            return

        print("Start sending file")
        self.filepointer = 0

        while self.filepointer < self.data.__len__() or not self.retransmissionQueue.empty():

            while not self.dupAckQueue.empty():
                syn, packet = self.dupAckQueue.get_nowait()
                self.sendbuffer.put((packet.to_bytes(), self.peer))
                self.retransmissionQueue.put((syn, packet))
                print(f"Retry of segment {str(syn)}")
                if self.process_ack(self.timeout) is False:
                    self.dupAckQueue.put((syn, packet))

            i = 0
            if not self.retransmissionQueue.empty():
                packets = []
                try:
                    while not self.retransmissionQueue.empty() and i < self.window:
                        packets.append(self.retransmissionQueue.get_nowait())
                        i += 1
                except queue.Empty:
                    pass

                for syn, packet in packets:
                    self.sendbuffer.put((packet.to_bytes(), self.peer))
                    self.retransmissionQueue.put((syn, packet))
                    print(f"Sent segment with sequence number {str(syn)} again")

            while i < self.window and self.filepointer < self.data.__len__():
                self.send_next_packet()
                i += 1

            # Packets have been added to the buffer once. Now check for Ack packets.
            self.process_acks(self.timeout)

        terminated = self.start_termination(self.destination)
        while not terminated:
            terminated = self.start_termination(self.destination)

        self.sender.stop()
        self.receiver.stop()
        self.sender.join()
        self.receiver.join()
        self.sock.close()
        return True

    def get_next_packet(self):
        if self.filepointer >= self.data.__len__():
            return False

        header = Header(self.id, self.synnumber, self.acknumber, 0b0, self.window, len(self.data[self.filepointer]), 0)
        packet = Packet(header, Payload(self.data[self.filepointer]))
        packet.payload.fill()
        packet.set_checksum()

        self.filepointer += 1
        return packet

    def send_next_packet(self):
        packet = self.get_next_packet()
        if packet is False:
            return False
        self.sendbuffer.put((packet.to_bytes(), self.peer))
        self.retransmissionQueue.put((packet.header.synnumber, packet))
        # print("Sent segment with a sequence number of " + str(self.synnumber))
        self.synnumber += 1
        return packet

    def process_acks(self, timeout):
        self.timelimit = time.time() + timeout
        duplicateack = False
        i = self.retransmissionQueue.qsize()
        while (not self.retransmissionQueue.empty()) and time.time() <= self.timelimit and i > 0:
            try:
                packet, addr = self.receivebuffer.get(True, self.timelimit - time.time())
                packet = Packet.from_bytes(packet)
                # print("Received ACK with an ack-number of " + str(packet.header.acknumber))
                if packet.header.id == self.id and \
                        packet.check_checksum() and \
                        packet.header.ack == 1 and \
                        time.time() <= self.timelimit:
                    i -= 1

                    if packet.header.acknumber == self.lastack\
                            and duplicateack is False:
                        # Duplicate ACK detected
                        duplicateack = True
                        syn, lastPacket = self.retransmissionQueue.get_nowait()
                        self.dupAckQueue.put((syn, lastPacket))

                    # Empty retransmissionQueue as long as packets are ACKed
                    syn, lastPacket = self.retransmissionQueue.get_nowait()
                    while packet.header.acknumber > syn:
                        syn, lastPacket = self.retransmissionQueue.get_nowait()
                    self.retransmissionQueue.put((syn, lastPacket))
                    # Update lastack
                    self.lastack = packet.header.acknumber
            except queue.Empty:
                pass

    def process_ack(self, timeout):
        self.timelimit = time.time() + timeout
        try:
            packet, addr = self.receivebuffer.get(True, self.timelimit - time.time())
            packet = Packet.from_bytes(packet)
            # print("Received ACK with an ack-number of " + str(packet.header.acknumber))
            if packet.header.id == self.id and \
                    packet.check_checksum() and \
                    packet.header.ack == 1 and \
                    time.time() <= self.timelimit:

                if packet.header.acknumber >= self.synnumber:
                    return True

                # Empty retransmissionQueue as long as packets are ACKed
                syn, lastPacket = self.retransmissionQueue.get_nowait()
                while packet.header.acknumber > syn:
                    syn, lastPacket = self.retransmissionQueue.get_nowait()
                self.retransmissionQueue.put((syn, lastPacket))

                if packet.header.acknumber < self.synnumber:
                    # Duplicate ACK detected
                    syn, lastPacket = self.retransmissionQueue.get_nowait()
                    self.dupAckQueue.put((syn, lastPacket))
                else:
                    return True

                # Update lastack
                self.lastack = packet.header.acknumber
        except queue.Empty:
            return False


if __name__ == "__main__":
    # Handle arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--window", help="Define bTCP window size", type=int, default=100)
    parser.add_argument("-t", "--timeout", help="Define bTCP timeout in milliseconds", type=int, default=1000)
    parser.add_argument("-i","--input", help="File to send", default="falcon9.png")
    args = parser.parse_args()

    clientrunner = Runners.ClientRunner(args.window, args.timeout, args.input)
    clientrunner.start()
