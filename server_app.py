#!/usr/local/bin/python3

import socket, argparse
from Packet import Header, Packet, Payload
import queue
import btcp_implementation
import time
import Runners
from btcp.btcp_socket import BTCPSocket, BTCPStates
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
import contextlib
"""This exposes a constant bytes object called TEST_BYTES_128MIB which, as the
name suggests, is 128 MiB in size. You can send it, receive it, and check it
for equality on the receiving end.

Pycharm may complain about an unresolved reference. This is a lie. It simply
cannot deal with a python source file this large so it cannot resolve the
reference. Python itself will run it fine, though.

You can also use the file large_input.py as-is for file transfer.
"""
from large_input import TEST_BYTES_128MIB

class bTCP_client(btcp_implementation.Btcp):

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
            
    def flagfinder(self, flag):
        if flag == "0x0":
            return False, False, False
        elif flag == "0x1":
            return False, False, True
        elif flag == "0x2":
            return False, True, False
        elif flag == "0x3":
            return False, True, True
        elif flag == "0x4":
            return True, False, False
        elif flag == "0x5":
            return True, False, True
        elif flag == "0x6":
            return True, True, False
        elif flag == "0x7":
            return True, True, True

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

            #if queue not empty
            while not self.dupAckQueue.empty():

                #get syn and data
                syn, data = self.dupAckQueue.get_nowait()
                
                #send data away
                self.sendbuffer.put((data, self.peer))
                self.retransmissionQueue.put((syn, data))
                print(f"Retry of segment {str(syn)}")
                if self.process_ack(self.timeout) is False:
                    self.dupAckQueue.put((syn, data))

            it = 0
            if not self.retransmissionQueue.empty():
                packets = []
                with contextlib.suppress(queue.Empty):
                    while not self.retransmissionQueue.empty() and it < self.window:
                        packets.append(self.retransmissionQueue.get_nowait())
                        it += 1
                for syn, packet in packets:
                    self.sendbuffer.put((packet.to_bytes(), self.peer))
                    self.retransmissionQueue.put((syn, packet))
                    print(f"Sent segment with sequence number {str(syn)} again")

            while it < self.window and self.filepointer < self.data.__len__():
                self.send_next_packet()
                it += 1

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
        
        #create socket
        sock = BTCPSocket(self.window, self.timeout)
        
        #create payload
        payload = self.data[self.filepointer] + bytes(1000 - len(self.data[self.filepointer]))
            
        #create checksum
        checksum = sock.in_cksum(sock.build_segment_header(self.synnumber, self.acknumber, False, False, False, self.window, len(self.data[self.filepointer]), 0)
                                 + payload)
        
        #build header including checksum
        header = sock.build_segment_header(self.synnumber, self.acknumber, False, False, False, self.window, len(self.data[self.filepointer]), checksum)
        
        #header = Header(self.id, self.synnumber, self.acknumber, 0b0, self.window, len(self.data[self.filepointer]), 0)
        #packet = Packet(header, Payload(self.data[self.filepointer]))
        #packet.payload.fill()
        #packet.set_checksum()

        self.filepointer += 1
        return header+payload, self.synnumber

    def send_next_packet(self):
        packet, syn = self.get_next_packet()
        if packet is False:
            return False
        self.sendbuffer.put((packet, self.peer))
        self.retransmissionQueue.put((syn, packet))
        # print("Sent segment with a sequence number of " + str(self.synnumber))
        self.synnumber += 1
        return packet

    def process_acks(self, timeout):
        self.timelimit = time.time() + timeout
        duplicateack = False
        i = self.retransmissionQueue.qsize()
        
        while (not self.retransmissionQueue.empty()) and time.time() <= self.timelimit and i > 0:
            with contextlib.suppress(queue.Empty):
                data, addr = self.receivebuffer.get(True, self.timelimit - time.time())
                
                #build socket
                sock = BTCPSocket(self.window, self.timeout)
                
                #check if header is long enough
                if len(data) < 16:
                    raise ValueError("header is not long enough")
                
                #get first 10 data bytes
                headr = data[:10]
                
                #get payload
                payload = data[10:]
                
                #generate temp header
                header_temp = sock.unpack_segment_header(headr)
                
                #unpack header
                syn_number = header_temp[0]
                ack_number = header_temp[1]
                flag_byte = hex(header_temp[2])
                window = header_temp[3]
                length = header_temp[4]
                
                #this is the given checksum
                checksum = header_temp[5]
                
                #get flag bools
                synf, ackf, finf = flagfinder(flag_byte)
                
                #we calculate our own checksum from our data to compare
                checksum_comp = sock.in_cksum(sock.build_segment_header(syn_number, ack_number, synf, ackf, finf, window, length, 0)
                                            + payload)
                
                #packet = Packet.from_bytes(packet)
                
                # print("Received ACK with an ack-number of " + str(packet.header.acknumber))
                if (checksum == checksum_comp 
                    and ackf 
                    and time.time() <= self.timelimit):
                    i -= 1

                    if ack_number == self.lastack\
                            and duplicateack is False:
                        # Duplicate ACK detected
                        duplicateack = True
                        syn, lastPacket = self.retransmissionQueue.get_nowait()
                        self.dupAckQueue.put((syn, lastPacket))

                    # Empty retransmissionQueue as long as packets are ACKed
                    syn, lastPacket = self.retransmissionQueue.get_nowait()
                    while ack_number > syn:
                        syn, lastPacket = self.retransmissionQueue.get_nowait()
                    self.retransmissionQueue.put((syn, lastPacket))
                    # Update lastack
                    self.lastack = ack_number

    def process_ack(self, timeout):
        self.timelimit = time.time() + timeout
        try:
            data, addr = self.receivebuffer.get(True, self.timelimit - time.time())
            
            #build socket
            sock = BTCPSocket(self.window, self.timeout)
            
            #check if header is long enough
            if len(data) < 16:
                raise ValueError("header is not long enough")
            
            #get first 10 data bytes
            headr = data[:10]
            
            #get payload
            payload = data[10:]
            
            #generate temp header
            header_temp = sock.unpack_segment_header(headr)
            
            #unpack header
            syn_number = header_temp[0]
            ack_number = header_temp[1]
            flag_byte = hex(header_temp[2])
            window = header_temp[3]
            length = header_temp[4]
            
            #this is the given checksum
            checksum = header_temp[5]
            
            #get flag bools
            synf, ackf, finf = flagfinder(flag_byte)
            
            #we calculate our own checksum from our data to compare
            checksum_comp = sock.in_cksum(sock.build_segment_header(syn_number, ack_number, synf, ackf, finf, window, length, 0)
                                        + payload)
                
           # packet = Packet.from_bytes(packet)
            # print("Received ACK with an ack-number of " + str(packet.header.acknumber))
            if (checksum == checksum_comp 
                and ackf 
                and time.time() <= self.timelimit):

                if ack_number >= self.synnumber:
                    return True

                # Empty retransmissionQueue as long as packets are ACKed
                syn, lastPacket = self.retransmissionQueue.get_nowait()
                while ack_number > syn:
                    syn, lastPacket = self.retransmissionQueue.get_nowait()
                self.retransmissionQueue.put((syn, lastPacket))

                if ack_number < self.synnumber:
                    # Duplicate ACK detected
                    syn, lastPacket = self.retransmissionQueue.get_nowait()
                    self.dupAckQueue.put((syn, lastPacket))
                else:
                    return True

                # Update lastack
                self.lastack = ack_number
        except queue.Empty:
            return False


if __name__ == "__main__":
    # Handle arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--window",
                        help="Define bTCP window size",
                        type=int, default=100)
    parser.add_argument("-t", "--timeout",
                        help="Define bTCP timeout in milliseconds",
                        type=int, default=100)
    parser.add_argument("-i", "--input",
                        help="File to send",
                        default="large_input.py")
    args = parser.parse_args()

    clientrunner = Runners.ClientRunner(args.window, args.timeout, args.input)
    clientrunner.start()
