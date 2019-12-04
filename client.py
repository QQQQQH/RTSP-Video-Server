import socket
import threading


def close_socket(sock):
    if sock:
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()


class Client:
    def __init__(self):
        self.clientRtpPort = None
        self.clientRtcpPort = None
        self.serverRtpSocket = None
        self.serverRtspSocket = None
        self.moviePath = None
        self.continueEvent = threading.Event()
        self.continueEvent.set()

    def close(self):
        if self.serverRtpSocket:
            close_socket(self.serverRtpSocket)
        if self.serverRtspSocket:
            close_socket(self.serverRtspSocket)

        self.clientRtpPort = None
        self.clientRtcpPort = None

        self.moviePath = None
        self.continueEvent.set()
