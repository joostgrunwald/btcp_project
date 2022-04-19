import socket
from btcp.btcp_socket import BTCPSocket, BTCPStates
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
from random import getrandbits

import queue


class BTCPClientSocket(BTCPSocket):
    """bTCP client socket
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
    """


    def __init__(self, window, timeout):
        """Constructor for the bTCP client socket. Allocates local resources
        and starts an instance of the Lossy Layer.

        You can extend this method if you need additional attributes to be
        initialized, but do *not* call connect from here.
        """
        super().__init__(window, timeout)
        self.connection = False
        self.window = window
        self.timeout = timeout
        self._lossy_layer = LossyLayer(self, CLIENT_IP, CLIENT_PORT, SERVER_IP, SERVER_PORT)

        # The data buffer used by send() to send data from the application
        # thread into the network thread. Bounded in size.
        self._sendbuf = queue.Queue(maxsize=1000)
        self._receivebuf = queue.Queue(maxsize=1000)

        #set socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        #set timeout in seconds
        self.socket.settimeout(1.5)


    ###########################################################################
    ### The following section is the interface between the transport layer  ###
    ### and the lossy (network) layer. When a segment arrives, the lossy    ###
    ### layer will call the lossy_layer_segment_received method "from the   ###
    ### network thread". In that method you should handle the checking of   ###
    ### the segment, and take other actions that should be taken upon its   ###
    ### arrival.                                                            ###
    ###                                                                     ###
    ### Of course you can implement this using any helper methods you want  ###
    ### to add.                                                             ###
    ###########################################################################

    def lossy_layer_segment_received(self, segment):
        """Called by the lossy layer whenever a segment arrives.

        Things you should expect to handle here (or in helper methods called
        from here):
            - checksum verification (and deciding what to do if it fails)
            - receiving syn/ack during handshake
            - receiving ack and registering the corresponding segment as being
              acknowledged
            - receiving fin/ack during termination
            - any other handling of the header received from the server

        Remember, we expect you to implement this *as a state machine!*
        """

        #TODO 1: unpack segment
        #TODO 2: give buffer to checksum generating function
        #TODO 3: check the value of TODO 2 to know if the checksum was valified

        pass # present to be able to remove the NotImplementedError without having to implement anything yet.
        raise NotImplementedError("No implementation of lossy_layer_segment_received present. Read the comments & code of client_socket.py.")


    def lossy_layer_tick(self):
        """Called by the lossy layer whenever no segment has arrived for
        TIMER_TICK milliseconds. Defaults to 100ms, can be set in constants.py.

        NOTE: Will NOT be called if segments are arriving; do not rely on
        simply counting calls to this method for an accurate timeout. If 10
        segments arrive, each 99 ms apart, this method will NOT be called for
        over a second!

        The primary use for this method is to be able to do things in the
        "network thread" even while no segments are arriving -- which would
        otherwise trigger a call to lossy_layer_segment_received.

        For example, checking for timeouts on acknowledgement of previously
        sent segments -- to trigger retransmission -- should work even if no
        segments are being received. Although you can't count these ticks
        themselves for the timeout, you can trigger the check from here.

        You will probably see some code duplication of code that doesn't handle
        the incoming segment among lossy_layer_segment_received and
        lossy_layer_tick. That kind of duplicated code would be a good
        candidate to put in a helper method which can be called from either
        lossy_layer_segment_received or lossy_layer_tick.
        """

        raise NotImplementedError("Only rudimentary implementation of lossy_layer_tick present. Read the comments & code of client_socket.py, then remove the NotImplementedError.")

        # Send all data available for sending.
        # Relies on an eventual exception to break from the loop when no data
        # is available.
        # You should be checking whether there's space in the window as well,
        # and storing the segments for retransmission somewhere.
        while True:
            try:
                # Get a chunk of data from the buffer, if available.
                chunk = self._sendbuf.get_nowait()
                datalen = len(chunk)
                if datalen < PAYLOAD_SIZE:
                    chunk = chunk + b'\x00' * (PAYLOAD_SIZE - datalen)
                segment = self.build_segment_header(0, 0, length=datalen) + chunk
                self._lossy_layer.send_segment(segment)
            except queue.Empty:
                # No data was available for sending.
                break


    ###########################################################################
    ### You're also building the socket API for the applications to use.    ###
    ### The following section is the interface between the application      ###
    ### layer and the transport layer. Applications call these methods to   ###
    ### connect, shutdown (disconnect), send data, etc. Conceptually, this  ###
    ### happens in "the application thread".                                ###
    ###                                                                     ###
    ### You *can*, from this application thread, send segments into the     ###
    ### lossy layer, i.e. you can call LossyLayer.send_segment(segment)     ###
    ### from these methods without ensuring that happens in the network     ###
    ### thread. However, if you do want to do this from the network thread, ###
    ### you should use the lossy_layer_tick() method above to ensure that   ###
    ### segments can be sent out even if no segments arrive to trigger the  ###
    ### call to lossy_layer_segment_received. When passing segments between ###
    ### the application thread and the network thread, remember to use a    ###
    ### Queue for its inherent thread safety.                               ###
    ###                                                                     ###
    ### Note that because this is the client socket, and our (initial)      ###
    ### implementation of bTCP is one-way reliable data transfer, there is  ###
    ### no recv() method available to the applications. You should still    ###
    ### be able to receive segments on the lossy layer, however, because    ###
    ### of acknowledgements and synchronization. You should implement that  ###
    ### above.                                                              ###
    ###########################################################################

    def connect(self):
        """Perform the bTCP three-way handshake to establish a connection.

        connect should *block* (i.e. not return) until the connection has been
        successfully established or the connection attempt is aborted. You will
        need some coordination between the application thread and the network
        thread for this, because the syn/ack from the server will be received
        in the network thread.

        Hint: assigning to a boolean or enum attribute in thread A and reading
        it in a loop in thread B (preferably with a short sleep to avoid
        wasting a lot of CPU time) ensures that thread B will wait until the
        boolean or enum has the expected value. We do not think you will need
        more advanced thread synchronization in this project.
        """

        #check if there is no connection yet
        if (self.connection):
            print("ERROR: there is already an connection present")
            #TODO: exception or termination of some kind?

        print("Starting phase one of three way handshake")
        
        #create random number
        seq_num = getrandbits(16)

        #flags 
        # TODO: create enum for flags
        # 0x1 = SYN, 0x2 = ACK, 0x3 = FIN
        # SYN and ACK =     0X1 | 0X2
        # check flag =      if (FLAG & 0x1) > 0: print("syn is set")

        #sequence number, ack number (empty yet), flags, window, data length
        #TODO: add packet/header class

        #we set checksum to 0 then calculate it
        temp_header = (seq_num, 0, '0x1', self.window, 0, 0)
        payload = bytes(1000)

        #set socket and generate checksum
        sock = BTCPSocket(self.window, self.timeout)
        checksum = sock.in_cksum(sock.build_segment_header(temp_header) + payload)

        #use checksum for full header
        header = (seq_num, 0, '0x1', self.window, 0, checksum)

        #pack header for usage inside pack and create packet
        pack = (sock.build_segment_header(header), payload)

        #add package to sendbuf
        self._sendbuf.put(pack)

        #use socket to send data to address
        done = False 
        while done == False:
            try: 
                #block if neccesarry until something is available, timeout = 1.5 seconds
                data, addr = self._sendbuf.get(True, 1.5)
                self.socket.sendto(data, addr)
            except queue.empty:
                pass
            #TODO: catch errors in except (OSERROR?)
        #TODO: send syn packet to server

        #get header checksum
        #set header checksum field to checksum

        # create syn packet (header + SYN payload)
        # calculate checksum of packet
        # send packet



        print("Starting phase two of three way handshake")

        print("Starting phase three of three way handshake")
        #TODO:
        # 1 The client randomly generates a 16-bit value, say x, puts this in the Sequence Number field
        # of a bTCP segment with the SYN flag set, and sends the segment to the server.

        # 2 is handled by the server

        # 3  The client puts y + 1 in the Acknowledgement Number
        # field of a bTCP segment with the ACK flag set. The Sequence Number field of that segment
        # is x + 1.

        #TODO: window size (section 2.6)

        #pass # present to be able to remove the NotImplementedError without having to implement anything yet.
        #raise NotImplementedError("No implementation of connect present. Read the comments & code of client_socket.py.")


        #we only return after finishing the connection
        self.connection = True
        print("Succesfully connected")
        return True


    def send(self, data):
        """Send data originating from the application in a reliable way to the
        server.

        This method should *NOT* block waiting for acknowledgement of the data.


        You are free to implement this however you like, but the following
        explanation may help to understand how sockets *usually* behave and you
        may choose to follow this concept as well:

        The way this usually works is that "send" operates on a "send buffer".
        Once (part of) the data has been successfully put "in the send buffer",
        the send method returns the number of bytes it was able to put in the
        buffer. The actual sending of the data, i.e. turning it into segments
        and sending the segments into the lossy layer, happens *outside* of the
        send method (e.g. in the network thread).
        If the socket does not have enough buffer space available, it is up to
        the application to retry sending the bytes it was not able to buffer
        for sending.

        Again, you should feel free to deviate from how this usually works.
        Note that our rudimentary implementation here already chunks the data
        in maximum 1008-byte bytes objects because that's the maximum a segment
        can carry. If a chunk is smaller we do *not* pad it here, that gets
        done later.
        """

        raise NotImplementedError("Only rudimentary implementation of send present. Read the comments & code of client_socket.py, then remove the NotImplementedError.")

        # Example with a finite buffer: a queue with at most 1000 chunks,
        # for a maximum of 985KiB data buffered to get turned into packets.
        # See BTCPSocket__init__() in btcp_socket.py for its construction.
        datalen = len(data)
        sent_bytes = 0
        while sent_bytes < datalen:
            # Loop over data using sent_bytes. Reassignments to data are too
            # expensive when data is large.
            chunk = data[sent_bytes:sent_bytes+PAYLOAD_SIZE]
            try:
                self._sendbuf.put_nowait(chunk)
                sent_bytes += len(chunk)
            except queue.Full:
                break
        return sent_bytes


    def shutdown(self):
        """Perform the bTCP three-way finish to shutdown the connection.

        shutdown should *block* (i.e. not return) until the connection has been
        successfully terminated or the disconnect attempt is aborted. You will
        need some coordination between the application thread and the network
        thread for this, because the fin/ack from the server will be received
        in the network thread.

        Hint: assigning to a boolean or enum attribute in thread A and reading
        it in a loop in thread B (preferably with a short sleep to avoid
        wasting a lot of CPU time) ensures that thread B will wait until the
        boolean or enum has the expected value. We do not think you will need
        more advanced thread synchronization in this project.
        """

        #TODO: section 2.3

        pass # present to be able to remove the NotImplementedError without having to implement anything yet.
        raise NotImplementedError("No implementation of shutdown present. Read the comments & code of client_socket.py.")

    ## NO MODIFICATIONS NEEDED BELOW HERE

    def close(self):
        """Cleans up any internal state by at least destroying the instance of
        the lossy layer in use. Also called by the destructor of this socket.

        Do not confuse with shutdown, which disconnects the connection.
        close destroys *local* resources, and should only be called *after*
        shutdown.

        Probably does not need to be modified, but if you do, be careful to
        gate all calls to destroy resources with checks that destruction is
        valid at this point -- this method will also be called by the
        destructor itself. The easiest way of doing this is shown by the
        existing code:
            1. check whether the reference to the resource is not None.
                2. if so, destroy the resource.
            3. set the reference to None.
        """
        if self._lossy_layer is not None:
            self._lossy_layer.destroy()
        self._lossy_layer = None


    def __del__(self):
        """Destructor. Do not modify."""
        self.close()
