
#!/usr/local/bin/python3
import threading
import queue 
import socket  

class send_packet(threading.Thread):

    def __init__(self, buf, socket):
        super().__init__()
        self.buf = buf
        self.socket = socket
        self.running = True

    def run(self):
        while self.running:
            try:
                data, addr = self.buf.get(True, 1)
                self.socket.sendto(data, addr)
            except queue.Empty:
                pass
            except OSError:
                break

    def stop(self):
        self.running = False

class receive_packet(threading.Thread):

    def __init__(self, buf, socket):
        super().__init__()
        self.buf = buf
        self.socket = socket
        self.running = True

    def run(self):
        while self.running:
            try:
                inf = self.socket.recvfrom(1016)
                self.buf.put_nowait(inf)
            except queue.Full:
                pass
            except socket.timeout:
                pass
            except OSError:
                break


    def stop(self):
        self.running = False     
