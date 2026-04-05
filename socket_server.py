"""ChitChat Server

Usage:
    python socket_server.py

Starts a TCP chat server on 127.0.0.1:1234. Run this before starting any
client. Multiple clients can connect simultaneously; every message sent by
one client is broadcast to all connected clients.

All connections and messages are logged to chitchat.log in the working
directory.
"""
import logging
import socket
import threading

logging.basicConfig(
    filename="chitchat.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ServerThread(threading.Thread):
    def __init__(self, server, client_socket):
        super().__init__(daemon=True)
        self.server = server
        self.client_socket = client_socket
        self.name_label = None
        self.reader = client_socket.makefile(mode="r", buffering=1, encoding="utf-8")
        self.writer = client_socket.makefile(mode="w", buffering=1, encoding="utf-8")

    def send(self, message):
        self.writer.write(message + "\n")
        self.writer.flush()

    def run(self):
        try:
            self.name_label = self.reader.readline().strip()
            logger.info("JOIN  [%s] from %s", self.name_label, self.client_socket.getpeername())
            self.server.broadcast(f"**[{self.name_label}] Entered**")
            self.server.broadcast_user_list()

            for data in self.reader:
                data = data.strip()
                if data.startswith("__IMG__:"):
                    logger.info("IMG   [%s]", self.name_label)
                    self.server.broadcast(f"__IMG__:{self.name_label}:{data[len('__IMG__:'):]}")
                else:
                    logger.info("MSG   [%s] %s", self.name_label, data)
                    self.server.broadcast(f"[{self.name_label}] {data}")
        except Exception as e:
            print(f"Error handling client communication: {e} ---->")  
        finally:
            self.server.remove_thread(self)
            self.server.broadcast(f"**[{self.name_label}] Left**")
            self.server.broadcast_user_list()
            try:
                addr = self.client_socket.getpeername()
                print(f"{addr} - [{self.name_label}] Exit")
                logger.info("LEAVE [%s] from %s", self.name_label, addr)
            except OSError:
                print(f"[{self.name_label}] Exit")
                logger.info("LEAVE [%s]", self.name_label)
            try:
                self.reader.close()
                self.writer.close()
                self.client_socket.close()
            except Exception:
                pass


class SocketServer:
    def __init__(self, host="127.0.0.1", port=1234):
        self.host = host
        self.port = port
        self.clients = []
        self.lock = threading.Lock()

    def add_thread(self, thread):
        with self.lock:
            self.clients.append(thread)

    def remove_thread(self, thread):
        with self.lock:
            self.clients.remove(thread)

    def get_user_list(self):
        with self.lock:
            return [t.name_label for t in self.clients if t.name_label]

    def broadcast_user_list(self):
        names = ",".join(self.get_user_list())
        self.broadcast(f"__USERS__:{names}")

    def broadcast(self, message):
        print(message)
        with self.lock:
            for client in self.clients:
                try:
                    client.send(message)
                except Exception:
                    pass

    def serve(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(50)
            print(f"\n Waiting for Client connection on {self.host}:{self.port}")

            while True:
                client_socket, addr = server_socket.accept()
                print(f"{addr} connect")
                logger.info("CONNECT %s", addr)

                thread = ServerThread(self, client_socket)
                self.add_thread(thread)
                thread.start()


if __name__ == "__main__":
    SocketServer().serve()
