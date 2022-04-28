#!/usr/local/bin/python3
import socket, argparse
from struct import *
import btcp_implementation
from Packet import Header, Packet, Payload
import queue
import Runners
import time
from btcp.btcp_socket import BTCPSocket, BTCPStates
from btcp.lossy_layer import LossyLayer
from btcp.constants import *

class bTCP_server(btcp_implementation.Btcp):

    def __init__(self, source, window = 100, timeout = 10):
        super().__init__(source, window, timeout)
        self.reassembleQueue = queue.PriorityQueue()
        self.reassemblesyns = []
        self.data = []
        self.finished = False

    def begin(self):
        self.start()

        # Start Handshake
        while not self.connected:
            self.connected = self.listen()

    def end(self):
        self.finished = True
        
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
        
    def receive_file(self, file):
        print("Start receiving file")
        self.data = []

        while self.connected and not self.finished:

            #set socket and generate checksum
            sock = BTCPSocket(self.window, self.timeout)
        
            #get information
            data, addr = self.receivebuffer.get()

            #check if header is long enough
            if len(data) < 16:
                raise ValueError("header is not long enough")
            
            #get first 10 data bytes
            headr = data[:10]
            
            #get payload
            payload = data[10:]
        
            #buiild temp headr
            header_temp = sock.unpack_segment_header(headr)
        
            #unpack header
            syn_number = header_temp[0]
            ack_number = header_temp[1]
            flag_byte = hex(header_temp[2])
            window = header_temp[3]
            length = header_temp[4]
                
            #this is the given checksum
            checksum = header_temp[5]
            
            #get bools for flags
            syn, ack, fin = flagfinder(flag_byte)
            
            #we calculate our own checksum from our data to compare
            checksum_comp = sock.in_cksum(sock.build_segment_header(syn_number, ack_number, syn, ack, fin, window, length, 0)
                                      + payload)
            
            #check checksum integrity
            if checksum == checksum_comp:
                
                #disable connection at FIN
                if fin == True:
                    print("FIN rec")
                    self.connected = False
                    
                #if syn = ack
                elif syn_number == self.acknumber:
                    self.add_data(header_temp, payload)
                    self.send_ack()
                    
                #no order
                else:
                    self.add_data(header_temp, payload)
                    self.send_ack()
                    
        timeout = time.time() + 2*self.timeout
        while not self.finished and time.time() < timeout:
            self.finished = self.respond_termination(addr, headr, payload)
        if not self.finished:
            print("Terminated because of timeout. No ACK packet received from client.")

        print("All data has been received.")
        print("Starting writing data to file")
        file.from_packets(file.path, self.data)

        self.sender.stop()
        self.receiver.stop()
        self.sender.join()
        self.receiver.join()
        self.sock.close()

    def add_data(self, header, payload):
        #unpack header
        syn_number = header[0]
        ack_number = header[1]
        flag_byte = hex(header[2])
        window = header[3]
        length = header[4]
            
        #this is the given checksum
        checksum = header[5]
        try:
            while True:
                
                #if self.ack = segment.syn
                if syn_number == self.acknumber:
                    
                    #add data till length
                    self.data.append(payload[:length])
                    
                    #increment ack
                    self.acknumber += 1
                    
                    #get data from que
                    syn, header, payload = self.reassembleQueue.get_nowait()
                    
                    #remove syn_number from queue
                    self.reassemblesyns.remove(syn_number)
                    
                #if segment.syn > self.ack
                elif syn_number > self.acknumber:
                    
                    #add to queue if not in queue
                    if syn_number not in self.reassemblesyns:
                        self.reassembleQueue.put((syn_number, header, payload))
                        self.reassemblesyns.append(syn_number)
                    break
                else:
                    break
        except queue.Empty:
            return
        except TypeError:
            print("Error")
        return

    def send_ack(self):
        #create default payload
        payload = bytes(1000)
        
        #create socket
        sock = BTCPSocket(self.window, self.timeout)
            
        #create checksum
        checksum = sock.in_cksum(sock.build_segment_header(self.synnumber, self.acknumber, False, True, False, self.window, 0, 0)
                                 + payload)
        
        #build header including checksum
        header = sock.build_segment_header(self.synnumber, self.acknumber, False, True, false, self.window, 0, checksum)
        
        #send packet
        self.sendbuffer.put((header + payload, self.peer))


if __name__ == "__main__":
    #Handle arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--window",
                        help="Define bTCP window size",
                        type=int, default=100)
    parser.add_argument("-t", "--timeout",
                        help="Define bTCP timeout in milliseconds",
                        type=int, default=100)
    parser.add_argument("-o", "--output",
                        help="Where to store the file",
                        default="output.file")
    args = parser.parse_args()

    serverrunner = Runners.ServerRunner(args.window, args.timeout, args.output)
    serverrunner.start()
