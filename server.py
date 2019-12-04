import socket
import time
import re
import random
import rtsp
import ts
import os
import threading
from rtpPacket import RtpPacket


def close_socket(sock):
    if sock:
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()


class Server:
    HOST = ''
    LOCAL_HOST = '127.0.0.1'
    SERVER_LISTEN_PORT = 8554

    MAX_BUF = 1024
    MAX_SEQNUM = 65535

    MOVIE_DIR_PATH = 'movie'

    RTP_VERSION = 2
    RTP_PAYLOAD_TYPE_TS = 33

    def __init__(self):
        self.listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listenSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)

        self.serverRtpSocket = None
        self.serverRtspSocket = None

        self.clientRtpPort = None
        self.clientRtcpPort = None

        self.moviePath = None
        self.continueEvent = threading.Event()
        self.continueEvent.set()

        self.work()

    def reset_server(self):
        close_socket(self.serverRtpSocket)
        close_socket(self.serverRtspSocket)

        self.clientRtpPort = None
        self.clientRtcpPort = None

        self.moviePath = None
        self.continueEvent.set()

    def bind_socket(self):
        try:
            self.listenSocket.bind((self.HOST, self.SERVER_LISTEN_PORT))
        except Exception as e:
            print('bind server listen socket error: ')
            print(e)
        else:
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

    def send_response(self, response):
        response = response.encode('utf-8')
        print(response)
        self.serverRtspSocket.send(response)

    def handle_OPTIONS(self, requestDic):
        pattern = r'rtsp://.*/(.*)'
        res = re.search(pattern, requestDic['url'])
        self.moviePath = self.MOVIE_DIR_PATH + '/' + res.group(1)
        fileName = str(os.path.splitext(self.moviePath)[0])
        if os.path.isfile(self.moviePath):
            if not os.path.isfile(fileName + '.ts'):
                os.system('ffmpeg -y -i %s.mp4 -vcodec copy -acodec copy -vbsf h264_mp4toannexb %s.ts'
                          % (fileName, fileName))
        self.moviePath = fileName + '.ts'
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Public': 'OPTIONS, DESCRIBE, SETUP, PLAY',
            'Session': ''.join(random.sample('0123456789', 8))
        }
        response = rtsp.generate_response(responseDic)
        self.send_response(response)

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
        self.send_response(response)

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
        self.send_response(response)

    def handle_PLAY(self, requestDic):
        pattern = r'npt=(\d*)-'
        res = re.search(pattern, requestDic['Range'])
        startTime = int(res.group(1))
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Range': 'npt=0-',
            'Session': requestDic['Session'] + ';timeout=60',
        }
        if startTime == 0:
            if not self.continueEvent.is_set():
                self.continueEvent.set()
            else:
                length = os.path.getsize(self.moviePath)
                pos = length // ts.TS_PACKET_SIZE * ts.TS_PACKET_SIZE - ts.TS_PACKET_SIZE + 1
                totalTime = 0
                with open(self.moviePath, 'rb') as f:
                    if f.seek(pos, 0) > 0:
                        while True:
                            tsPacket = f.read(ts.TS_PACKET_SIZE)
                            totalTime = ts.get_ts_pcr(tsPacket)
                            if totalTime > 0:
                                break
                            if f.seek(-2 * ts.TS_PACKET_SIZE, 1) == -1:
                                break
                responseDic['Range'] += str(int(totalTime))
            response = rtsp.generate_response(responseDic)
            self.send_response(response)
            threading.Thread(target=self.send_movie).start()
        else:
            close_socket(self.serverRtpSocket)
            startPos = 0
            preTime = 0
            with open(self.moviePath, 'rb') as f:
                while True:
                    tsPacket = f.read(ts.TS_PACKET_SIZE)
                    if not tsPacket:
                        break
                    getTime = int(ts.get_ts_pcr(tsPacket))
                    # if getTime > 0:
                    #     print(getTime, startTime)
                    if preTime <= startTime <= getTime:
                        startPos = f.tell() - ts.TS_PACKET_SIZE
                        break
                    preTime = getTime
            responseDic['Range'] = 'npt=' + str(int(getTime)) + '-'
            response = rtsp.generate_response(responseDic)
            self.send_response(response)
            threading.Thread(target=self.send_movie, args=(startPos,)).start()

    def handle_PAUSE(self, requestDic):
        self.continueEvent.clear()
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Session': requestDic['Session']
        }
        response = rtsp.generate_response(responseDic)
        self.send_response(response)

    def handle_TEARDOWN(self, requestDic):
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Session': requestDic['Session']
        }
        response = rtsp.generate_response(responseDic)
        self.send_response(response)
        self.reset_server()

    def parse_request(self, request):
        print(request)
        request = request.decode('utf-8')
        requestLines = request.split('\r\n')
        requestDic = rtsp.parse_request(requestLines)
        [method, url, version] = requestLines[0].strip().split(' ')
        requestDic['method'], requestDic['url'] = method, url

        if method == 'SETUP':
            self.handle_SETUP(requestDic)
        elif method == 'OPTIONS':
            self.handle_OPTIONS(requestDic)
        elif method == 'DESCRIBE':
            self.handle_DESCRIBE(requestDic)
        elif method == 'PLAY':
            self.handle_PLAY(requestDic)
        elif method == 'PAUSE':
            self.handle_PAUSE(requestDic)
        elif method == 'TEARDOWN':
            self.handle_TEARDOWN(requestDic)
        else:
            return

    def send_movie(self, startPos=0):
        self.serverRtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.serverRtpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        rtpPacket = RtpPacket()
        with open(self.moviePath, 'rb') as f:
            f.seek(startPos, 0)
            cnt = 0
            for rtpPayload in ts.get_ts_payload(f):
                rtpPacket.set_payload(rtpPayload)
                self.continueEvent.wait()
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
                    # print(rtpPacket.seqNum)
                    cnt += 1
                    if cnt >= 5:
                        cnt = 0
                        time.sleep(0.001)
        print('send movie finished')
