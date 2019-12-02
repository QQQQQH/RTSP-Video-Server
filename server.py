import socket
import time
import re
import random
import rtsp
import ts
from rtpPacket import RtpPacket
from h264 import get_H264_frame
from h264 import send_H264_frame


class Server:
    HOST = ''
    LOCAL_HOST = '127.0.0.1'
    RTSP_PORT = 8554
    RTP_PORT = 55532
    RTCP_PORT = 55533
    MAX_BUF = 1024
    MAX_SEQNUM = 65535
    H264_FILE_NAME = 'test/1.h264'
    TS_FILE_NAME = 'test/1.ts'
    RTP_VERSION = 2
    RTP_PAYLOAD_TYPE_H264 = 96
    RTP_PAYLOAD_TYPE_TS = 33
    H264_READ_LEN = 500000

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverRtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.serverRtcpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.serverRtspSocket = None
        self.clientRtpPort = None
        self.clientRtcpPort = None
        self.set_scoket()

    def set_scoket(self):
        # set socket
        self.serverRtpSocket.bind((self.HOST, self.RTP_PORT))
        self.serverRtcpSocket.bind((self.HOST, self.RTCP_PORT))

        self.socket.bind((self.HOST, self.RTSP_PORT))
        self.socket.listen(10)
        print('Accepting')
        accepted = self.socket.accept()
        self.serverRtspSocket = accepted[0]
        print('Accepted: ')
        print(accepted[1])
        print('\n')

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
        response = rtsp.generate_response(responseDic, append=sdp)
        return response

    def handle_SETUP(self, requestDic):
        pattern = r'client_port=(\d*)-(\d*)'
        res = re.search(pattern, requestDic['Transport'])
        self.clientRtpPort, self.clientRtcpPort = int(res.group(1)), int(res.group(2))
        responseDic = {
            'CSeq': requestDic['CSeq'],
            'Transport': requestDic['Transport'] + ';server_port=%d-%d' % (self.RTP_PORT, self.RTCP_PORT),
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

    def recv_request(self):
        # parse request
        try:
            request = self.serverRtspSocket.recv(self.MAX_BUF)
            if not request:
                return
        except:
            return
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
            self.send_ts()

        return

    def send_h264(self):
        rtpPacket = RtpPacket(self.RTP_VERSION, 0, 0, 0, 0, self.RTP_PAYLOAD_TYPE_H264, 0, 0, 0x88923423)
        with open(self.H264_FILE_NAME, 'rb') as f:
            while True:
                frame = get_H264_frame(f, self.H264_READ_LEN)
                if not frame:
                    return False
                if frame[2] == 1:
                    startCode = 3
                else:
                    startCode = 4
                frameSize = len(frame) - startCode
                sentBytes = send_H264_frame(self.serverRtpSocket,
                                            (self.LOCAL_HOST, self.clientRtpPort),
                                            rtpPacket,
                                            frame[startCode:],
                                            frameSize)
                rtpPacket.timeStamp += 90000 // 25
                time.sleep(1.0 / 25)

    def send_ts(self):
        rtpPacket = RtpPacket(self.RTP_VERSION, 0, 0, 0, 0, self.RTP_PAYLOAD_TYPE_TS, 0, 0, 0x88923423)
        with open(self.TS_FILE_NAME, 'rb') as f:
            for rtpPayload in ts.get_ts_payload(f):
                rtpPacket.set_payload(rtpPayload)
                self.serverRtpSocket.sendto(rtpPacket.get_packet(), (self.LOCAL_HOST, self.clientRtpPort))
                if rtpPacket.seqNum == self.MAX_SEQNUM:
                    rtpPacket.seqNum = 0
                else:
                    rtpPacket.seqNum += 1
                print(rtpPacket.seqNum)
                time.sleep(0.001)

    def work(self):
        while True:
            self.recv_request()
