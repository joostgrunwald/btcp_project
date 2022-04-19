
#!/usr/local/bin/python3
import threading
import queue 
import socket  

class send_packet(threading.Thread):
    def __init__(self, buf, socket):
        super().__init__()
        self.socket = socket
        self.terminate = False
        self.buf = buf
        
    def terminate(self):
        self.terminate = True
        
    def send_packet(self):
        while not self.terminate():
            try: 
                data, addr = self.buf.get(True, 1.5)
                self.socket.sendto(data, addr)
            except queue.Empty:
                pass
            except OSError:
                break
        
    
class receive_packet(threading.Thread):
    def __init__(self, buf, socket):
        super().__init__()
        self.socket = socket
        self.terminate = False
        self.buf = buf
    
    def terminate(self):
        self.terminate = True 
            
    def receive_packet(self):
        while not self.terminate():
            try: 
                info = self.socket.recvfrom(1016)
                self.socket.put_nowait(info)
            except queue.Full or socket.timeout:
                pass
            except OSError:
                break
