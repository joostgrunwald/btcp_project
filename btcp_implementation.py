#!/usr/local/bin/python3
import contextlib
import socket, argparse
from Packet import Header, Packet, Payload
from Poster import send_packet, receive_packet
import queue
from random import getrandbits
from btcp.btcp_socket import BTCPSocket, BTCPStates
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
import binascii

class Btcp:
    """_summary_
    
    A client application makes use of the services provided by bTCP by calling
    connect, send, shutdown, and close.

    You're implementing the transport layer, exposing it to the application
    layer as a (variation on) socket API.

    To implement the transport layer, you also need to interface with the
    network (lossy) layer. This happens by both calling into it
    (LossyLayer.send_segment) and providing callbacks for it
    (BTCPClientSocket.lossy_layer_segment_received, lossy_layer_tick).

    Your implementation will operate in two threads, the network thread,
    where the lossy layer "lives" and where your callbacks will be called from,
    and the application thread, where the application calls connect, send, etc.
    This means you will need some thread-safe information passing between
    network thread and application thread.
    Writing a boolean or enum attribute in one thread and reading it in a loop
    in another thread should be sufficient to signal state changes.
    Lists, however, are not thread safe, so to pass data and segments around
    you probably want to use Queues, or a similar thread safe collection.
    
    TODO: add server
    TODO: payload usage
    TODO: clean
    """
    
    def __init__(self, source, window, timeout):
        """Constructor for the bTCP client socket. Allocates local resources
        and starts an instance of the Lossy Layer.

        You can extend this method if you need additional attributes to be
        initialized, but do *not* call connect from here.
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
        self.receiver = receive_packet(self.receivebuffer, self.sock)
        self.sendbuffer = queue.Queue(1000)
        self.sender = send_packet(self.sendbuffer, self.sock)

    def start(self):
        self.sock.bind(self.source)
        self.receiver.start()
        self.sender.start()

    def listen(self):
        if self.connected:
            print("ERROR: there is already an connection present (server)")
            exit(0)

        # Wait for handshake
        data, addr = self.receivebuffer.get()
        
        #check if header is long enough
        if len(data) < 16:
            raise ValueError("header is not long enough")
        
        #specify payload
        payload = bytes(1000)
        
        #get first 10 data bytes
        headr = data[:10]
        
        #create socket and build header
        sock = BTCPSocket(self.window, self.timeout)
        header_temp = sock.unpack_segment_header(headr)
        
        #unpack header
        syn_number = header_temp[0]
        ack_number = header_temp[1]
        flag_byte = hex(header_temp[2])
        window = header_temp[3]
        length = header_temp[4]
        
        #this is the given checksum
        checksum = header_temp[5]
        
        if str(flag_byte) != "0x4":
            #print("Flag byte s1 is wrong")
            #print(flag_byte)
            return False
        
        #we calculate our own checksum from our data to compare
        checksum_comp = sock.in_cksum(sock.build_segment_header(syn_number, ack_number, True, False, False, window, length, 0)
                                      + payload)
        
        if ( header_temp is None
            #check that SYN == 1
            or syn_number == 0
            #check that ack != 1
            or ack_number != 0
            #check that the checksum works
            or checksum != checksum_comp
            
        ):
            #if any of these conditions is true, we return False for the entire function
            return False
        
        #output
        print(f"A client from {addr} tries to connect.")

        #adjust window
        if window < self.window:
            self.window = window
            
        #! send SYN-ACK package
        #ack = syn + 1
        ack_num = syn_number + 1
        prev_ack = ack_num
        
        #generate random sequence number
        seq_num = getrandbits(16)
        
        #create new checksum
        checksum = sock.in_cksum(sock.build_segment_header(seq_num, ack_num, True, True, False, self.window, 0, 0)
                                 + payload)
        
        #build header including checksum
        header = sock.build_segment_header(seq_num, ack_num, True, True, False, self.window, 0, checksum)
        
        #send syn-ack to client
        self.sendbuffer.put((header + payload, addr))
        
        #! receive ACK package

        # Wait for ACK
        with contextlib.suppress(queue.Empty):
            data, addr = self.receivebuffer.get(True, self.timeout)
                        
            #get packet 
            ackpacket = Packet.from_bytes(data)
            
            #check if header is long enough
            if len(data) < 16:
                raise ValueError("header is not long enough")
            
            #get first 10 data bytes
            headr = data[:10]
            
            #create socket and build header
            header_temp = sock.unpack_segment_header(headr)
            
            #unpack header
            syn_number = header_temp[0]
            ack_number = header_temp[1]
            flag_byte = hex(header_temp[2])
            window = header_temp[3]
            length = header_temp[4]
            
            #this is the given checksum
            checksum = header_temp[5]
            
            if str(flag_byte) != "0x2":
                print("Flag byte s2 is wrong")
                print(flag_byte)
                return False
            
            #we calculate our own checksum from our data to compare
            checksum_comp = sock.in_cksum(sock.build_segment_header(syn_number, ack_number, False, True, False, window, length, 0)
                                        + payload)
        
            #if the conditions dont hold we pass the try
            if ( header_temp is None
                #check that SYN == 1
                or syn_number != prev_ack
                #check that ack != 1
                or ack_number != seq_num + 1
                #check that the window works
                or self.window != window 
                #check that the checksum works
                or checksum != checksum_comp
                
            ):
                print("headers do not match for ACK")
                pass
            else:
                print("Ack went fine")

        print(f"Server connection established with {str(addr)}")
        self.peer = addr
        self.acknumber = ack_num
        self.connected = True

        return True

    def connect(self, destination):
        if self.connected:
            print("ERROR: there is already an connection present (client)")
            exit()
            #TODO: exception or termination of some kind?

        print(f"Starting phase one of three way handshake with {str(destination)}")
        
        #create random number
        seq_num = getrandbits(16)

        #flags 
        # 0x1 = SYN, 0x2 = ACK, 0x3 = FIN
        # SYN and ACK =     0X1 | 0X2
        # check flag =      if (FLAG & 0x1) > 0: print("syn is set")
        
        #we set checksum to 0 then calculate it
        payload = bytes(1000)
        
        #set socket and generate checksum
        sock = BTCPSocket(self.window, self.timeout)
        
        checksum = sock.in_cksum(sock.build_segment_header(seq_num, 0, True, False, False, self.window, 0, 0)
                                 + payload)
        
        #build header including checksum
        header = sock.build_segment_header(seq_num, 0, True, False, False, self.window, 0, checksum)
        
        self.sendbuffer.put((header + payload, destination))

        print(f"Starting phase two of three way handshake with {str(destination)}")
        
        # Syn-Ack ontvangen
        try:
            data, addr = self.receivebuffer.get(True, self.timeout)
        except queue.Empty:
            return False

        #check if header is long enough
        if len(data) < 16:
            raise ValueError("header is not long enough")
        
        #get first 10 data bytes
        headr = data[:10]
        
        #unpack header
        header_temp = sock.unpack_segment_header(headr)
        
        #unpack header
        syn_number = header_temp[0]
        ack_number = header_temp[1]
        flag_byte = hex(header_temp[2])
        window = header_temp[3]
        length = header_temp[4]
        
        #this is the given checksum
        checksum = header_temp[5]
        
        if str(flag_byte) != "0x6":
            #print("Flag byte c1 is wrong")
            #print(flag_byte)
            return False
        
        #we calculate our own checksum from our data to compare
        checksum_comp = sock.in_cksum(sock.build_segment_header(syn_number, ack_number, True, True, False, window, length, 0)
                                      + payload)
                

        #check that header is not empty
        if ( header_temp is None
            #check that ACK = SYN + 1
            or ack_number != seq_num + 1 
            #check that syn is defined
            or syn_number == 0
            #check that the checksum works
            or (checksum != checksum_comp)
            
        ):
            return False
        
        self.window = window
        
        #! Sending ack
        
        #ack = y + 1
        ack_number = syn_number + 1
        
        #syn = x + 1
        syn_number = seq_num + 1
        
        #checksum generation
        checksum = sock.in_cksum(sock.build_segment_header(syn_number, ack_number, False, True, False, self.window, 0, 0)
                                 + payload)
        
        #build header including checksum
        header = sock.build_segment_header(syn_number, ack_number, False, True, False, self.window, 0, checksum)
        
        #send 
        self.sendbuffer.put((header + payload, destination))

        print(f"Client connection established with {str(destination)}")
        self.peer = destination
        self.synnumber = syn_number
        self.connected = True

        return True

    def start_termination(self, destination):
        # FIN Packet sturen
        print("Started phase one of client termination")
        
        syn_number1 = self.synnumber
        
        payload = bytes(1000)
        
        #set socket and generate checksum
        sock = BTCPSocket(self.window, self.timeout)
        
        #create checksum
        checksum = sock.in_cksum(sock.build_segment_header(syn_number1, 0, False, False, True, self.window, 0, 0)
                                 + payload)
        
        #build header including checksum
        header = sock.build_segment_header(syn_number1, 0, False, False, True, self.window, 0, checksum)
        
        #send packet
        self.sendbuffer.put((header + payload, destination))

        #Wait until receival of FIN-ACK segment
        with contextlib.suppress(queue.Empty):
            data, addr = self.receivebuffer.get(True, self.timeout)
            
        #check if header is long enough
        if len(data) < 16:
            raise ValueError("header is not long enough")
        
        #get first 10 data bytes
        headr = data[:10]
        
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
        
        #check the flag byte
        if str(flag_byte) != "0x3":
            print("Flag byte ct1 is wrong")
            print(flag_byte)
            return False
        
        #we calculate our own checksum from our data to compare
        checksum_comp = sock.in_cksum(sock.build_segment_header(syn_number, ack_number, False, True, True, window, length, 0)
                                      + payload)
            
        #conditions
        if header_temp is None or addr != destination or (checksum_comp != checksum):
            return False

        #! SENDING ACK as response
        #create checksum
        checksum = sock.in_cksum(sock.build_segment_header(syn_number1, 0, False, True, False, self.window, 0, 0)
                                 + payload)
        
        #build header including checksum
        header = sock.build_segment_header(syn_number1, 0, False, True, False, self.window, 0, checksum)
        
        #send packet
        self.sendbuffer.put((header + payload, destination))
        
        print(f"Connection terminated with {str(destination)}")
        return True

    def respond_termination(self, destination, finpacket):
        
        print("started phase one of server termination")
        
        payload = bytes(1000)
        
        #set socket and generate checksum
        sock = BTCPSocket(self.window, self.timeout)
        
        #get possible FIN segment
        with contextlib.suppress(queue.Empty):
            data, addr = self.receivebuffer.get(True, self.timeout)
            
        #check if header is long enough
        if len(data) < 16:
            raise ValueError("header is not long enough")
        
        #get first 10 data bytes
        headr = data[:10]
        
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
        
        #check the flag byte
        if str(flag_byte) != "0x1":
            print("Flag byte st1 is wrong")
            print(flag_byte)
            return False
        
        #we calculate our own checksum from our data to compare
        checksum_comp = sock.in_cksum(sock.build_segment_header(syn_number, ack_number, False, False, True, window, length, 0)
                                      + payload)
            
        #conditions
        if header_temp is None or addr != destination or (checksum_comp != checksum):
            return False
        
        #! SENDING FIN-ACK AS RESPONSE
        
        print("started phase two of server termination")
        
        #create checksum
        checksum = sock.in_cksum(sock.build_segment_header(syn_number + 1, 0, False, True, True, self.window, 0, 0)
                                 + payload)
        
        #build header including checksum
        header = sock.build_segment_header(syn_number + 1, 0, False, True, True, self.window, 0, checksum)
        
        #send packet
        self.sendbuffer.put((header + payload, destination))
    
        #! RECEIVING ACK AND TERMINATING SERVER

        #get data and address again
        with contextlib.suppress(queue.Empty):
            data, addr = self.receivebuffer.get(True, self.timeout)

        #check if header is long enough
        if len(data) < 16:
            raise ValueError("header is not long enough")
        
        #get first 10 data bytes
        headr = data[:10]
        
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
        
        #check the flag byte
        if str(flag_byte) != "0x2":
            print("Flag byte st2 is wrong")
            print(flag_byte)
            return False
        
        #we calculate our own checksum from our data to compare
        checksum_comp = sock.in_cksum(sock.build_segment_header(syn_number, ack_number, False, True, True, window, length, 0)
                                      + payload)
            
        #conditions
        if header_temp is None or (checksum_comp != checksum):
            return False
        
        #end reached
        print(f"Connection terminated with {str(destination)}")
        return True
