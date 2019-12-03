import socket
import time
import re
import random
import rtsp
import ts
import threading
from rtpPacket import RtpPacket


def close_socket(sock):
    if sock:
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
        sock = None


class Server:
    HOST = ''
    LOCAL_HOST = '127.0.0.1'
    SERVER_LISTEN_PORT = 8554

    MAX_BUF = 1024
    MAX_SEQNUM = 65535

    MOVIE_FILE_NAME = 'test/2.ts'

    RTP_VERSION = 2
    RTP_PAYLOAD_TYPE_TS = 33

    def __init__(self):
        self.listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)

        self.serverRtpSocket = None
        self.serverRtspSocket = None

        self.clientRtpPort = None
        self.clientRtcpPort = None

        self.work()

    def reset_server(self):
        close_socket(self.serverRtpSocket)
        close_socket(self.serverRtspSocket)

        self.clientRtpPort = None
        self.clientRtcpPort = None

    def bind_socket(self):
        try:
            self.listenSocket.bind((self.HOST, self.SERVER_LISTEN_PORT))
        except Exception as e:
            print('bind server listen socket error: ')
            print(e)
        finally:
            print('listen started at: ' + self.HOST + str(self.SERVER_LISTEN_PORT))

    def work(self):
        self.bind_socket()
        self.listenSocket.listen(10)
        while True:
            print('Accepting')
            accepted = self.listenSocket.accept()
            self.serverRtspSocket = accepted[0]
            print('Accepted: ')
            print(accepted[1])
            self.recv_request()

    def recv_request(self):
        while True:
            try:
                request = self.serverRtspSocket.recv(self.MAX_BUF)
            except Exception as e:
                print('server rtsp socket closed')
                print(e)
                break
            else:
                if not request:
                    print('client rtsp socket closed')
                    self.reset_server()
                    break
                self.parse_request(request)

    def handle_OPTIONS(self, requestDic):
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Public': 'OPTIONS, DESCRIBE, SETUP, PLAY',
            'Session': ''.join(random.sample('0123456789', 8))
        }
        response = rtsp.generate_response(responseDic)
        return response

    def handle_DESCRIBE(self, requestDic):
        sessionSdpDic = {
            'sessionId': str(int(time.time()))
        }
        sessionSdp = rtsp.generate_session_sdp(**sessionSdpDic)
        mediaSdpDic = {

        }
        mediaSdp = rtsp.generate_ts_media_sdp(**mediaSdpDic)
        sdp = sessionSdp + mediaSdp
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Content-type': 'application/sdp',
            'Content-length': len(sdp),
            'Session': requestDic['Session']
        }
        response = rtsp.generate_response(responseDic, sdp)
        return response

    def handle_SETUP(self, requestDic):
        pattern = r'client_port=(\d*)-(\d*)'
        res = re.search(pattern, requestDic['Transport'])
        self.clientRtpPort, self.clientRtcpPort = int(res.group(1)), int(res.group(2))
        responseDic = {
            'CSeq': requestDic['CSeq'],
            # 'Transport': requestDic['Transport'] + ';server_port=%d-%d' % (self.SERVER_RTP_PORT, self.SERVER_RTCP_PORT),
            'Transport': requestDic['Transport'],
            'Session': requestDic['Session']
        }
        response = rtsp.generate_response(responseDic)
        return response

    def handle_PLAY(self, requestDic):
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Range': requestDic['Range'],
            'Session': requestDic['Session'] + ';timeout=60',
        }
        response = rtsp.generate_response(responseDic)
        return response

    def parse_request(self, request):
        print(request)
        request = request.decode('utf-8')
        requestLines = request.split('\r\n')
        requestDic = rtsp.parse_request(requestLines)
        [method, url, version] = requestLines[0].strip().split(' ')
        requestDic['method'], requestDic['url'] = method, url

        if method == 'SETUP':
            response = self.handle_SETUP(requestDic)
        elif method == 'OPTIONS':
            response = self.handle_OPTIONS(requestDic)
        elif method == 'DESCRIBE':
            response = self.handle_DESCRIBE(requestDic)
        elif method == 'PLAY':
            response = self.handle_PLAY(requestDic)
        else:
            return
        response = response.encode('utf-8')
        print(response)
        self.serverRtspSocket.send(response)
        if method == 'PLAY':
            threading.Thread(target=self.send_movie).start()

    def send_movie(self):
        self.serverRtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.serverRtpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        rtpPacket = RtpPacket()
        with open(self.MOVIE_FILE_NAME, 'rb') as f:
            for rtpPayload in ts.get_ts_payload(f):
                rtpPacket.set_payload(rtpPayload)
                try:
                    self.serverRtpSocket.sendto(rtpPacket.get_packet(), (self.LOCAL_HOST, self.clientRtpPort))
                except Exception as e:
                    print('server rtp socket closed')
                    print(e)
                    break
                else:
                    if rtpPacket.seqNum == self.MAX_SEQNUM:
                        rtpPacket.seqNum = 0
                    else:
                        rtpPacket.seqNum += 1
                    print(rtpPacket.seqNum)
                    time.sleep(0.001)