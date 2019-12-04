import socket
import time
import re
import random
import rtsp
import ts
import os
import threading
from client import Client, close_socket
from rtpPacket import RtpPacket


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

        self.clientList = []

        self.serverRtpSocket = None
        self.serverRtspSocket = None

        self.clientRtpPort = None
        self.clientRtcpPort = None

        self.moviePath = None
        self.continueEvent = threading.Event()
        self.continueEvent.set()

        self.work()

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
            clt = Client()
            clt.serverRtspSocket = accepted[0]
            self.clientList.append(clt)
            print('Accepted: ')
            print(accepted[1])
            threading.Thread(target=self.recv_request, args=(clt,)).start()

    def recv_request(self, clt):
        while True:
            try:
                request = clt.serverRtspSocket.recv(self.MAX_BUF)
            except Exception as e:
                print('server rtsp socket closed')
                print(e)
                break
            else:
                if not request:
                    print('client rtsp socket closed')
                    clt.close()
                    break
                self.parse_request(request, clt)

    def send_response(self, response, clt):
        response = response.encode('utf-8')
        print(response)
        clt.serverRtspSocket.send(response)

    def handle_OPTIONS(self, requestDic, clt):
        pattern = r'rtsp://.*/(.*)'
        res = re.search(pattern, requestDic['url'])
        clt.moviePath = self.MOVIE_DIR_PATH + '/' + res.group(1)
        fileName = str(os.path.splitext(clt.moviePath)[0])
        if os.path.isfile(clt.moviePath):
            if not os.path.isfile(fileName + '.ts'):
                os.system('ffmpeg -y -i %s.mp4 -vcodec copy -acodec copy -vbsf h264_mp4toannexb %s.ts'
                          % (fileName, fileName))
        clt.moviePath = fileName + '.ts'
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Public': 'OPTIONS, DESCRIBE, SETUP, PLAY',
            'Session': ''.join(random.sample('0123456789', 8))
        }
        response = rtsp.generate_response(responseDic)
        self.send_response(response, clt)

    def handle_DESCRIBE(self, requestDic, clt):
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
        self.send_response(response, clt)

    def handle_SETUP(self, requestDic, clt):
        pattern = r'client_port=(\d*)-(\d*)'
        res = re.search(pattern, requestDic['Transport'])
        clt.clientRtpPort, clt.clientRtcpPort = int(res.group(1)), int(res.group(2))
        responseDic = {
            'CSeq': requestDic['CSeq'],
            # 'Transport': requestDic['Transport'] + ';server_port=%d-%d' % (self.SERVER_RTP_PORT, self.SERVER_RTCP_PORT),
            'Transport': requestDic['Transport'],
            'Session': requestDic['Session']
        }
        response = rtsp.generate_response(responseDic)
        self.send_response(response, clt)

    def handle_PLAY(self, requestDic, clt):
        pattern = r'npt=(\d*)-'
        res = re.search(pattern, requestDic['Range'])
        startTime = int(res.group(1))
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Range': 'npt=0-',
            'Session': requestDic['Session'] + ';timeout=60',
        }
        if startTime == 0:
            if not clt.continueEvent.is_set():
                clt.continueEvent.set()
            else:
                length = os.path.getsize(clt.moviePath)
                pos = length // ts.TS_PACKET_SIZE * ts.TS_PACKET_SIZE - ts.TS_PACKET_SIZE + 1
                totalTime = 0
                with open(clt.moviePath, 'rb') as f:
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
            self.send_response(response, clt)
            threading.Thread(target=self.send_movie, args=(clt,)).start()
        else:
            close_socket(clt.serverRtpSocket)
            startPos = 0
            preTime = 0
            with open(clt.moviePath, 'rb') as f:
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
            self.send_response(response, clt)
            threading.Thread(target=self.send_movie, args=(clt, startPos)).start()

    def handle_PAUSE(self, requestDic, clt):
        clt.continueEvent.clear()
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Session': requestDic['Session']
        }
        response = rtsp.generate_response(responseDic)
        self.send_response(response, clt)

    def handle_TEARDOWN(self, requestDic, clt):
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Session': requestDic['Session']
        }
        response = rtsp.generate_response(responseDic)
        self.send_response(response, clt)
        clt.close()

    def parse_request(self, request, clt):
        print(request)
        request = request.decode('utf-8')
        requestLines = request.split('\r\n')
        requestDic = rtsp.parse_request(requestLines)
        [method, url, version] = requestLines[0].strip().split(' ')
        requestDic['method'], requestDic['url'] = method, url

        if method == 'SETUP':
            self.handle_SETUP(requestDic, clt)
        elif method == 'OPTIONS':
            self.handle_OPTIONS(requestDic, clt)
        elif method == 'DESCRIBE':
            self.handle_DESCRIBE(requestDic, clt)
        elif method == 'PLAY':
            self.handle_PLAY(requestDic, clt)
        elif method == 'PAUSE':
            self.handle_PAUSE(requestDic, clt)
        elif method == 'TEARDOWN':
            self.handle_TEARDOWN(requestDic, clt)
        else:
            return

    def send_movie(self, clt, startPos=0):
        clt.serverRtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        clt.serverRtpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        rtpPacket = RtpPacket()
        with open(clt.moviePath, 'rb') as f:
            f.seek(startPos, 0)
            cnt = 0
            for rtpPayload in ts.get_ts_payload(f):
                rtpPacket.set_payload(rtpPayload)
                clt.continueEvent.wait()
                try:
                    clt.serverRtpSocket.sendto(rtpPacket.get_packet(), (self.LOCAL_HOST, clt.clientRtpPort))
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
