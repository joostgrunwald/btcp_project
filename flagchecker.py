import struct

syn_set = False
ack_set = True
fin_set = True
flag_byte = syn_set << 2 | ack_set << 1 | fin_set
print(flag_byte)
print(hex(flag_byte))
