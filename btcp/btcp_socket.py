import struct
from enum import Enum


class BTCPStates(Enum):
    """Enum class that helps you implement the bTCP state machine.

    These states are NOT exhaustive! We left out some states that you will need
    to implement the bTCP state machine correctly. The intention of this enum
    is to give you some idea for states and how simple the transitions between
    them are.

    Don't use the integer values of this enum directly. Always refer to them as
    BTCPStates.CLOSED etc.
    """
    CLOSED    = 0
    ACCEPTING = 1
    SYN_SENT  = 2
    SYN_RCVD  = 3
    ESTABLISHED  = 4 # There's an obvious state that goes here. Give it a name.
    FIN_SENT  = 5
    CLOSING   = 6
    
class BTCPSocket:
    """Base class for bTCP client and server sockets. Contains static helper
    methods that will definitely be useful for both sending and receiving side.
    """
    def __init__(self, window, timeout):
        self._window = window
        self._timeout = timeout


    @staticmethod
    def in_cksum(segment):
        """Compute the internet checksum of the segment given as argument.
        Consult lecture 3 for details.

        Our bTCP implementation always has an even number of bytes in a segment.

        Remember that, when computing the checksum value before *sending* the
        segment, the checksum field in the header should be set to 0x0000, and
        then the resulting checksum should be put in its place.
        """
        
        #TODO: we assume that we get the bTCP_header as input here
        
        # If we get an empty segment, return 0x0000
        if not segment:
            return 0x0000

        #pad zero's if odd
        if (len(segment) % 2 != 0): 
            segment += b"\x00"      

        #unpack segment due to big endian, use unsigned short
        packages = struct.iter_unpack("!H", segment)  
        #create initial checksum
        cksum = 0x0000           
        
        #add package to checksum
        for pk in packages:
            cksum += pk[0]                   

            #handle overflows
            if (cksum > 0xFFFF):             
                cksum = cksum & 0x0FFFF   
                cksum += 1                   

        #invert the checksum if it is not equal to 0xFFFF
        if (cksum != 0xFFFF):
            cksum = cksum.invert()

        return cksum
        
        #pass # present to be able to remove the NotImplementedError without having to implement anything yet.
        #raise NotImplementedError("No implementation of in_cksum present. Read the comments & code of btcp_socket.py.")


    @staticmethod
    def build_segment_header(seqnum, acknum,
                             syn_set=False, ack_set=False, fin_set=False,
                             window=0x01, length=0, checksum=0):
        """Pack the method arguments into a valid bTCP header using struct.pack

        This method is given because historically students had a lot of trouble
        figuring out how to pack and unpack values into / out of the header.
        We have *not* provided an implementation of the corresponding unpack
        method (see below), so inspect the code, look at the documentation for
        struct.pack, and figure out what this does, so you can implement the
        unpack method yourself.

        Of course, you are free to implement it differently, as long as you
        do so correctly *and respect the network byte order*.

        You are allowed to change the SYN, ACK, and FIN flag locations in the
        flags byte, but make sure to do so correctly everywhere you pack and
        unpack them.

        The method is written to have sane defaults for the arguments, so
        you don't have to always set all flags explicitly true/false, or give
        a checksum of 0 when creating the header for checksum computation.
        """
        flag_byte = syn_set << 2 | ack_set << 1 | fin_set
        return struct.pack("!HHBBHH",
                           seqnum, acknum, flag_byte, window, length, checksum)


    @staticmethod
    def unpack_segment_header(header):
        """Unpack the individual bTCP header field values from the header.

        Remember that Python supports multiple return values through automatic
        tupling, so it's easy to simply return all of them in one go rather
        than make a separate method for every individual field.
        """
        
        #TODO(maybe?) 
        #    (src_port, dst_port, seq_num, ack_num, flags, window, checksum) = header[0], header[1], header[2], header[3], header[4], header[5], header[6]
    	# payload = segment[header_length:]
        #Joost implemented 
        return struct.unpack("!HHBBHH", header)
        
        #pass
        #raise NotImplementedError("No implementation of unpack_segment_header present. Read the comments & code of btcp_socket.py. You should really implement the packing / unpacking of the header into field values before doing anything else!")
