HEADER_SIZE = 12


class RtpPacket:

    def __init__(self, version=2, padding=0, extension=0, cc=0, marker=0, payloadType=33, seqNum=0, timeStamp=0,
                 ssrc=0):
        self.version = version
        self.padding = padding
        self.extension = extension
        self.cc = cc
        self.marker = marker
        self.payloadType = payloadType
        self.seqNum = seqNum
        self.timeStamp = timeStamp
        self.ssrc = ssrc
        self.payload = None

    def get_packet(self):
        header = bytearray(HEADER_SIZE)
        header[0] = (self.version << 6) | (self.padding << 5) | (self.extension << 4) | self.cc
        header[1] = (self.marker << 7) | self.payloadType
        header[2] = (self.seqNum >> 8) & 255  # upper bits
        header[3] = self.seqNum & 255
        header[4] = self.timeStamp >> 24 & 255
        header[5] = self.timeStamp >> 16 & 255
        header[6] = self.timeStamp >> 8 & 255
        header[7] = self.timeStamp & 255
        header[8] = self.ssrc >> 24 & 255
        header[9] = self.ssrc >> 16 & 255
        header[10] = self.ssrc >> 8 & 255
        header[11] = self.ssrc & 255

        return header + self.payload

    def set_payload(self, payload):
        self.payload = payload

    def decode(self, byteStream):
        header = bytearray(byteStream[:HEADER_SIZE])
        self.version = int(header[0] >> 6)
        self.padding = int(header[0] >> 5 & 1)
        self.extension = int(header[0] >> 4 & 1)
        self.cc = int(header[0] & 15)
        self.marker = int(header[1] >> 7)
        self.payloadType = int(header[1] & 127)
        self.seqNum = int(header[2] << 8 | header[3])
        self.timeStamp = int(header[4] << 24 | header[5] << 16 | header[6] << 8 | header[7])
        self.ssrc = int(header[8] << 24 | header[9] << 16 | header[10] << 8 | header[11])

        self.payload = byteStream[HEADER_SIZE:]
